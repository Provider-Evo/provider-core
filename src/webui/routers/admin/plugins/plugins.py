"""WebUI 插件管理 API。"""
from __future__ import annotations

import asyncio
import json
import shutil
from typing import Any, Dict, List

import aiohttp.web

from src.foundation.logger import get_logger
from src.webui.routers.admin.plugins.plugin_support import (
    find_plugin_path_by_id,
    iter_plugin_dirs,
    plugins_root,
    read_manifest,
    read_plugin_changelog,
    reload_plugins_from_request,
    validate_plugin_id,
)
from src.webui.routers.admin.plugins.plugin_prog import reset_progress, update_progress
from src.webui.routers.admin.plugins.plugins_config import (
    plugins_config_bundle,
    plugins_config_get,
    plugins_config_put,
    plugins_config_reset,
)

__all__ = [
    "plugins_install",
    "plugins_installed",
    "plugins_list",
    "plugins_reload",
    "plugins_status",
    "plugins_config_get",
    "plugins_config_put",
    "plugins_config_bundle",
    "plugins_config_reset",
    "plugins_toggle",
    "plugins_uninstall",
    "plugins_update",
]

logger = get_logger(__name__)


def _build_installed_item(
    plugin_dir: Any,
    load_statuses: Dict[str, str],
    failure_reasons: Dict[str, str],
    circuit_statuses: Dict[str, str] | None = None,
) -> Dict[str, Any]:
    manifest = read_manifest(plugin_dir)
    plugin_id = str(manifest.get("id", ""))
    enabled = (plugin_dir / "_manifest.json").is_file()
    load_status = load_statuses.get(plugin_id, "unknown")
    if not enabled:
        load_status = "disabled"
    elif load_status == "unknown":
        load_status = "inactive"
    circuit = (circuit_statuses or {}).get(plugin_id, "closed")
    if not enabled:
        circuit = "disabled"
    elif load_status == "failed":
        circuit = "open"
    return {
        "id": plugin_id,
        "manifest": manifest,
        "path": plugin_dir.name,
        "enabled": enabled,
        "disabled": not enabled,
        "loaded": enabled and load_status == "loaded",
        "load_status": load_status,
        "circuit_status": circuit,
        "load_error": "" if not enabled or load_status != "failed" else failure_reasons.get(plugin_id, ""),
        "changelog": read_plugin_changelog(plugin_dir),
        "name": manifest.get("name", plugin_dir.name),
        "version": manifest.get("version", ""),
        "plugin_type": manifest.get("plugin_type", ""),
        "description": manifest.get("description", ""),
    }


async def plugins_list(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/admin/plugins — 已安装插件列表（简表）。"""
    payload = await plugins_installed(request)
    body = json.loads(payload.text or "{}")
    plugins = body.get("plugins", [])
    simplified = [
        {
            "path": p.get("path"),
            "id": p.get("id"),
            "name": p.get("name"),
            "version": p.get("version"),
            "plugin_type": p.get("plugin_type"),
            "description": p.get("description"),
            "enabled": p.get("enabled"),
            "loaded": p.get("loaded"),
            "load_status": p.get("load_status"),
            "load_error": p.get("load_error"),
        }
        for p in plugins
    ]
    return aiohttp.web.json_response({"plugins": simplified})


async def plugins_installed(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/admin/plugins/installed — 已安装插件列表（含 manifest、加载状态）。"""
    try:
        from src.core.server.plugins.runtime import get_plugin_runtime

        runtime = get_plugin_runtime()
        load_statuses = runtime.get_load_statuses()
        failure_reasons = runtime.get_plugin_load_failure_reasons()
        circuit_statuses = runtime.get_plugin_circuit_statuses()
    except Exception:
        load_statuses = {}
        failure_reasons = {}
        circuit_statuses = {}

    items: List[Dict[str, Any]] = []
    for plugin_dir in iter_plugin_dirs():
        items.append(_build_installed_item(plugin_dir, load_statuses, failure_reasons, circuit_statuses))

    return aiohttp.web.json_response(
        {"success": True, "plugins": items, "total": len(items)},
    )


async def plugins_status(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/admin/plugins/status — 运行时加载状态。"""
    try:
        from src.core.server.plugins.runtime import get_plugin_runtime

        runtime = get_plugin_runtime()
        statuses = runtime.get_load_statuses()
        failure_reasons = runtime.get_plugin_load_failure_reasons()
        summary = runtime.get_plugin_summary()
        recent_failures = runtime.get_recent_failures()
    except Exception as exc:
        logger.warning("插件状态读取失败: %s", exc)
        statuses = {}
        failure_reasons = {}
        summary = {"loaded": 0, "failed": 0, "inactive": 0}
        recent_failures = []
    return aiohttp.web.json_response({
        "statuses": statuses,
        "failure_reasons": failure_reasons,
        "recent_failures": recent_failures,
        "summary": summary,
    })


async def plugins_reload(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/admin/plugins/reload — 热重载全部插件。"""
    await update_progress("reload", 10, "正在热重载插件...", operation="reload")
    try:
        summary = await reload_plugins_from_request(request)
        await update_progress("done", 100, "热重载完成", operation="reload")
        return aiohttp.web.json_response({"status": "ok", "summary": summary})
    except Exception as exc:
        await update_progress("error", 100, str(exc), operation="reload", error=str(exc))
        raise
    finally:
        reset_progress()


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

    if plugin_id and not validate_plugin_id(plugin_id):
        return aiohttp.web.json_response({"error": "invalid plugin_id"}, status=400)

    await update_progress("start", 5, "准备安装...", operation="install", plugin_id=plugin_id or None)
    try:
        from provider_sdk.runtime.installer import install_plugin_from_git

        await update_progress("clone", 20, "正在克隆仓库...", operation="install", plugin_id=plugin_id or None)
        dest = install_plugin_from_git(url, plugins_root(), ref=ref)
        await update_progress("reload", 70, "正在加载 {}...".format(dest.name), operation="install", plugin_id=plugin_id or None)

        # 异步重载，避免阻塞响应
        import asyncio
        asyncio.ensure_future(reload_plugins_from_request(request, reload_app=False))
        await update_progress("done", 100, "已安装 {}".format(dest.name), operation="install", plugin_id=plugin_id or None)
        return aiohttp.web.json_response({"status": "ok", "path": str(dest.name)})
    except Exception as exc:
        logger.error("插件安装失败: %s", exc)
        await update_progress("error", 100, str(exc), operation="install", error=str(exc), plugin_id=plugin_id or None)
        return aiohttp.web.json_response({"error": str(exc)}, status=500)
    finally:
        reset_progress()


async def plugins_uninstall(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/admin/plugins/uninstall — 删除插件目录。"""
    try:
        body = await request.json()
    except Exception:
        return aiohttp.web.json_response({"error": "invalid json"}, status=400)

    folder = str(body.get("path") or "").strip()
    plugin_id = str(body.get("plugin_id") or "").strip()

    if plugin_id and not folder:
        plugin_path = find_plugin_path_by_id(plugin_id)
        if plugin_path:
            folder = plugin_path.name

    if not folder or ".." in folder:
        return aiohttp.web.json_response({"error": "invalid path"}, status=400)

    target = plugins_root() / folder
    if not target.is_dir():
        return aiohttp.web.json_response({"error": "not found"}, status=404)

    if target.is_symlink():
        return aiohttp.web.json_response({"error": "symlink not allowed"}, status=400)

    try:
        await update_progress("remove", 30, "正在删除 {}...".format(folder), operation="uninstall")
        shutil.rmtree(target)
        await update_progress("reload", 70, "正在热重载...", operation="uninstall")
        import asyncio
        asyncio.ensure_future(reload_plugins_from_request(request, reload_app=False))
        await update_progress("done", 100, "卸载完成", operation="uninstall")
        return aiohttp.web.json_response({"status": "ok"})
    except Exception as exc:
        logger.error("插件卸载失败: %s", exc)
        await update_progress("error", 100, str(exc), operation="uninstall", error=str(exc))
        return aiohttp.web.json_response({"error": str(exc)}, status=500)
    finally:
        reset_progress()


async def plugins_update(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/admin/plugins/update — 更新插件（Git pull）。"""
    try:
        body = await request.json()
    except Exception:
        return aiohttp.web.json_response({"error": "invalid json"}, status=400)

    plugin_id = str(body.get("plugin_id") or "").strip()
    if not plugin_id:
        return aiohttp.web.json_response({"error": "plugin_id required"}, status=400)

    plugin_path = find_plugin_path_by_id(plugin_id)
    if not plugin_path:
        return aiohttp.web.json_response({"error": "plugin not found"}, status=404)

    if (plugin_path / ".git").is_dir():
        try:
            await update_progress("pull", 20, "正在 git pull...", operation="update", plugin_id=plugin_id)
            proc = await asyncio.create_subprocess_exec(
                "git",
                "-C",
                str(plugin_path),
                "pull",
                "--ff-only",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                await update_progress("error", 100, stderr.decode(errors="ignore"), operation="update", error="git pull failed", plugin_id=plugin_id)
                return aiohttp.web.json_response({
                    "error": "git pull failed: {}".format(stderr.decode(errors="ignore")),
                }, status=500)
            await update_progress("reload", 70, "正在热重载...", operation="update", plugin_id=plugin_id)
            import asyncio
            asyncio.ensure_future(reload_plugins_from_request(request, reload_app=False))
            await update_progress("done", 100, "更新完成", operation="update", plugin_id=plugin_id)
            return aiohttp.web.json_response({
                "status": "ok",
                "output": stdout.decode(errors="ignore"),
            })
        except Exception as exc:
            await update_progress("error", 100, str(exc), operation="update", error=str(exc), plugin_id=plugin_id)
            return aiohttp.web.json_response({"error": str(exc)}, status=500)
        finally:
            reset_progress()

    return aiohttp.web.json_response({"error": "非 Git 安装的插件不支持更新"}, status=400)


async def plugins_toggle(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/admin/plugins/toggle — 切换插件启用/禁用。"""
    plugin_id = request.match_info.get("plugin_id", "")
    if not plugin_id:
        try:
            body = await request.json()
            plugin_id = str(body.get("plugin_id") or "").strip()
        except Exception:
            plugin_id = ""
    if not plugin_id:
        return aiohttp.web.json_response({"error": "plugin_id required"}, status=400)

    plugin_path = find_plugin_path_by_id(plugin_id)
    if not plugin_path:
        return aiohttp.web.json_response({"error": "plugin not found"}, status=404)

    manifest_enabled = plugin_path / "_manifest.json"
    manifest_disabled = plugin_path / "_manifest.json.disabled"

    if manifest_enabled.is_file():
        manifest_enabled.rename(manifest_disabled)
        enabled = False
    elif manifest_disabled.is_file():
        manifest_disabled.rename(manifest_enabled)
        enabled = True
    else:
        return aiohttp.web.json_response({"error": "manifest not found"}, status=404)

    await update_progress("reload", 50, "正在热重载...", operation="toggle", plugin_id=plugin_id)
    try:
        from src.core.server import REGISTRY_KEY, SESSION_KEY

        registry = request.app.get(REGISTRY_KEY)
        session = request.app.get(SESSION_KEY)
        if registry is not None and session is not None:
            await registry.sync_plugin_manifest(plugin_id, session, reload_app=False)
        runtime = registry._plugin_runtime() if registry else None
        summary = runtime.get_plugin_summary() if runtime else {"loaded": 0, "failed": 0, "inactive": 0}
        await update_progress("done", 100, "切换完成", operation="toggle", plugin_id=plugin_id)
        return aiohttp.web.json_response({"status": "ok", "enabled": enabled, "summary": summary})
    finally:
        reset_progress()
