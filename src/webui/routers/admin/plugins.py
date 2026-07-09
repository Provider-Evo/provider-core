"""WebUI 插件管理 API。"""
from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp.web

from src.logger import get_logger
from src.paths import project_root

__all__ = [
    "plugins_list",
    "plugins_install",
    "plugins_uninstall",
    "plugins_update",
    "plugins_status",
    "plugins_config_get",
    "plugins_config_put",
    "plugins_toggle",
]

logger = get_logger(__name__)


def _plugins_root() -> Path:
    return project_root / "plugins"


def _iter_plugin_dirs() -> List[Path]:
    root = _plugins_root()
    if not root.is_dir():
        return []
    out: List[Path] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if (child / "_manifest.json").is_file() or (child / "_manifest.json.disabled").is_file():
            out.append(child)
    return out


def _read_manifest(plugin_dir: Path) -> Dict[str, Any]:
    for name in ("_manifest.json", "_manifest.json.disabled"):
        path = plugin_dir / name
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _validate_plugin_id(plugin_id: str) -> bool:
    """校验插件 ID 合法性。"""
    if not plugin_id:
        return False
    if "/" in plugin_id or "\\" in plugin_id or ".." in plugin_id:
        return False
    if "\x00" in plugin_id:
        return False
    return True


def _find_plugin_path_by_id(plugin_id: str) -> Optional[Path]:
    """通过 manifest ID 查找插件目录。"""
    for plugin_dir in _iter_plugin_dirs():
        manifest = _read_manifest(plugin_dir)
        if manifest.get("id", "").lower() == plugin_id.lower():
            return plugin_dir
    return None


async def plugins_list(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/admin/plugins — 已安装插件目录与 manifest（含运行时状态）。"""
    try:
        from src.core.plugins.runtime import get_plugin_runtime
        runtime = get_plugin_runtime()
        load_statuses = runtime.get_load_statuses()
        failure_reasons = runtime.get_plugin_load_failure_reasons()
    except Exception:
        load_statuses = {}
        failure_reasons = {}

    items: List[Dict[str, Any]] = []
    for plugin_dir in _iter_plugin_dirs():
        manifest = _read_manifest(plugin_dir)
        plugin_id = manifest.get("id", "")
        enabled = (plugin_dir / "_manifest.json").is_file()
        load_status = load_statuses.get(plugin_id, "unknown")

        items.append({
            "path": plugin_dir.name,
            "id": plugin_id,
            "name": manifest.get("name", plugin_dir.name),
            "version": manifest.get("version", ""),
            "plugin_type": manifest.get("plugin_type", ""),
            "description": manifest.get("description", ""),
            "enabled": enabled,
            "loaded": load_status == "loaded",
            "load_status": load_status,
            "load_error": failure_reasons.get(plugin_id, ""),
        })
    return aiohttp.web.json_response({"plugins": items})


async def plugins_status(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/admin/plugins/status — 运行时加载状态。"""
    try:
        from src.core.plugins.runtime import get_plugin_runtime

        runtime = get_plugin_runtime()
        statuses = runtime.get_load_statuses()
        failure_reasons = runtime.get_plugin_load_failure_reasons()
        summary = runtime.get_plugin_summary()
    except Exception as exc:
        logger.warning("插件状态读取失败: %s", exc)
        statuses = {}
        failure_reasons = {}
        summary = {"loaded": 0, "failed": 0, "inactive": 0}
    return aiohttp.web.json_response({
        "statuses": statuses,
        "failure_reasons": failure_reasons,
        "summary": summary,
    })


async def plugins_install(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/admin/plugins/install — 从 Git URL 安装插件。"""
    try:
        body = await request.json()
    except Exception:
        return aiohttp.web.json_response({"error": "invalid json"}, status=400)

    url = str(body.get("url") or "").strip()
    ref = str(body.get("ref") or "").strip()
    plugin_id = str(body.get("plugin_id") or "").strip()

    if not url:
        return aiohttp.web.json_response({"error": "url required"}, status=400)

    # 校验插件 ID
    if plugin_id and not _validate_plugin_id(plugin_id):
        return aiohttp.web.json_response({"error": "invalid plugin_id"}, status=400)

    try:
        from provider_sdk.runtime.installer import install_plugin_from_git

        dest = install_plugin_from_git(url, _plugins_root(), ref=ref)
    except Exception as exc:
        logger.error("插件安装失败: %s", exc)
        return aiohttp.web.json_response({"error": str(exc)}, status=500)

    return aiohttp.web.json_response({"status": "ok", "path": str(dest.name)})


async def plugins_uninstall(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/admin/plugins/uninstall — 删除插件目录。"""
    try:
        body = await request.json()
    except Exception:
        return aiohttp.web.json_response({"error": "invalid json"}, status=400)

    folder = str(body.get("path") or "").strip()
    plugin_id = str(body.get("plugin_id") or "").strip()

    # 通过 plugin_id 查找路径
    if plugin_id and not folder:
        plugin_path = _find_plugin_path_by_id(plugin_id)
        if plugin_path:
            folder = plugin_path.name

    if not folder or ".." in folder:
        return aiohttp.web.json_response({"error": "invalid path"}, status=400)

    target = _plugins_root() / folder
    if not target.is_dir():
        return aiohttp.web.json_response({"error": "not found"}, status=404)

    # 安全检查：拒绝符号链接
    if target.is_symlink():
        return aiohttp.web.json_response({"error": "symlink not allowed"}, status=400)

    try:
        shutil.rmtree(target)
    except Exception as exc:
        logger.error("插件卸载失败: %s", exc)
        return aiohttp.web.json_response({"error": str(exc)}, status=500)

    return aiohttp.web.json_response({"status": "ok"})


async def plugins_update(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/admin/plugins/update — 更新插件（Git pull 或重新克隆）。"""
    try:
        body = await request.json()
    except Exception:
        return aiohttp.web.json_response({"error": "invalid json"}, status=400)

    plugin_id = str(body.get("plugin_id") or "").strip()
    if not plugin_id:
        return aiohttp.web.json_response({"error": "plugin_id required"}, status=400)

    plugin_path = _find_plugin_path_by_id(plugin_id)
    if not plugin_path:
        return aiohttp.web.json_response({"error": "plugin not found"}, status=404)

    # Git 安装的插件：直接 git pull
    if (plugin_path / ".git").is_dir():
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "-C", str(plugin_path), "pull", "--ff-only",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                return aiohttp.web.json_response({
                    "error": f"git pull failed: {stderr.decode(errors='ignore')}",
                }, status=500)
            return aiohttp.web.json_response({
                "status": "ok",
                "output": stdout.decode(errors="ignore"),
            })
        except Exception as exc:
            return aiohttp.web.json_response({"error": str(exc)}, status=500)
    else:
        return aiohttp.web.json_response({
            "error": "非 Git 安装的插件不支持更新",
        }, status=400)


async def plugins_config_get(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/admin/plugins/config/{plugin_id} — 获取插件配置。"""
    plugin_id = request.match_info.get("plugin_id", "")
    plugin_path = _find_plugin_path_by_id(plugin_id)
    if not plugin_path:
        return aiohttp.web.json_response({"error": "plugin not found"}, status=404)

    # 读取 config.toml
    config_path = plugin_path / "config.toml"
    if config_path.is_file():
        try:
            import tomlkit
            config = tomlkit.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            config = {}
    else:
        config = {}

    # 读取 schema
    schema_path = plugin_path / "config_schema.json"
    schema = {}
    if schema_path.is_file():
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    return aiohttp.web.json_response({
        "plugin_id": plugin_id,
        "config": config,
        "schema": schema,
    })


async def plugins_config_put(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """PUT /v1/admin/plugins/config/{plugin_id} — 更新插件配置。"""
    plugin_id = request.match_info.get("plugin_id", "")
    plugin_path = _find_plugin_path_by_id(plugin_id)
    if not plugin_path:
        return aiohttp.web.json_response({"error": "plugin not found"}, status=404)

    try:
        body = await request.json()
    except Exception:
        return aiohttp.web.json_response({"error": "invalid json"}, status=400)

    config_data = body.get("config", {})
    if not isinstance(config_data, dict):
        return aiohttp.web.json_response({"error": "config must be dict"}, status=400)

    config_path = plugin_path / "config.toml"
    try:
        import tomlkit
        if config_path.is_file():
            existing = tomlkit.loads(config_path.read_text(encoding="utf-8"))
        else:
            existing = tomlkit.document()

        # 深度合并
        def _merge(base: dict, patch: dict) -> dict:
            for k, v in patch.items():
                if isinstance(v, dict) and isinstance(base.get(k), dict):
                    _merge(base[k], v)
                else:
                    base[k] = v
            return base

        _merge(existing, config_data)
        config_path.write_text(tomlkit.dumps(existing), encoding="utf-8")
    except Exception as exc:
        logger.error("插件配置保存失败: %s", exc)
        return aiohttp.web.json_response({"error": str(exc)}, status=500)

    return aiohttp.web.json_response({"status": "ok"})


async def plugins_toggle(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/admin/plugins/toggle — 切换插件启用/禁用。"""
    plugin_id = request.match_info.get("plugin_id", "")
    plugin_path = _find_plugin_path_by_id(plugin_id)
    if not plugin_path:
        return aiohttp.web.json_response({"error": "plugin not found"}, status=404)

    manifest_enabled = plugin_path / "_manifest.json"
    manifest_disabled = plugin_path / "_manifest.json.disabled"

    if manifest_enabled.is_file():
        # 禁用：重命名为 .disabled
        manifest_enabled.rename(manifest_disabled)
        return aiohttp.web.json_response({"status": "ok", "enabled": False})
    elif manifest_disabled.is_file():
        # 启用：重命名为正常
        manifest_disabled.rename(manifest_enabled)
        return aiohttp.web.json_response({"status": "ok", "enabled": True})
    else:
        return aiohttp.web.json_response({"error": "manifest not found"}, status=404)
