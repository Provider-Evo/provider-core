
from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Dict

import aiohttp.web

from src.foundation.config import get_config_manager, reload_config, write_config
from src.foundation.paths import config_dir
from src.webui.data.services.schema.panel_schema import CONFIG_PANEL_SCHEMA

__all__ = [
    "config_get",
    "config_put",
    "config_reload",
    "config_schema_get",
    "config_raw_get",
    "config_raw_put",
]


def _main_config_path() -> Path:
    path = config_dir() / "main_config.toml"
    if not path.is_file():
        mgr = get_config_manager()
        if mgr._config_path is not None:
            path = mgr._config_path
    return path


def _parse_toml_text(raw_content: str) -> Dict[str, Any]:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

    data = tomllib.load(io.BytesIO(raw_content.encode("utf-8")))
    if not isinstance(data, dict):
        raise ValueError("root must be a TOML table")
    return data


def _load_main_config_dict() -> Dict[str, Any]:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

    path = _main_config_path()
    if not path.is_file():
        return {}
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    return data if isinstance(data, dict) else {}


async def config_get(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/config — 返回 main_config.toml 完整结构。"""
    del request
    try:
        return aiohttp.web.json_response(_load_main_config_dict())
    except Exception as exc:
        return aiohttp.web.json_response({"error": str(exc)}, status=500)


async def config_put(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """PUT /v1/config — 写入 main_config.toml 并热重载。"""
    try:
        payload = await request.json()
    except Exception:
        return aiohttp.web.json_response({"error": "invalid JSON body"}, status=400)
    if not isinstance(payload, dict):
        return aiohttp.web.json_response(
            {"error": "config body must be an object"}, status=400
        )
    ok = await write_config(payload)
    if not ok:
        return aiohttp.web.json_response({"error": "write failed"}, status=500)
    return aiohttp.web.json_response(
        {"status": "ok", "message": "main_config.toml saved and reloaded"},
    )


async def config_reload(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/config/reload — 从磁盘重新加载 main_config.toml。"""
    del request
    try:
        await reload_config()
    except Exception as exc:
        return aiohttp.web.json_response({"error": str(exc)}, status=500)
    return aiohttp.web.json_response(
        {"status": "ok", "message": "Config reloaded from main_config.toml"},
    )


async def config_schema_get(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/admin/config/schema — 配置面板字段 schema。"""
    del request
    return aiohttp.web.json_response(CONFIG_PANEL_SCHEMA)


async def config_raw_get(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/config/raw — 返回 main_config.toml 原始 TOML 文本。"""
    del request
    path = _main_config_path()
    if not path.is_file():
        return aiohttp.web.json_response({"error": "config file not found"}, status=404)
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:
        return aiohttp.web.json_response({"error": str(exc)}, status=500)
    return aiohttp.web.json_response({"success": True, "content": content})


async def config_raw_put(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/config/raw — 写入 main_config.toml 原始 TOML 并热重载。"""
    try:
        payload = await request.json()
    except Exception:
        return aiohttp.web.json_response({"error": "invalid JSON body"}, status=400)
    if not isinstance(payload, dict):
        return aiohttp.web.json_response(
            {"error": "body must be an object"}, status=400
        )
    raw_content = payload.get("raw_content")
    if not isinstance(raw_content, str):
        return aiohttp.web.json_response(
            {"error": "raw_content must be a string"}, status=400
        )
    try:
        _parse_toml_text(raw_content)
    except Exception as exc:
        return aiohttp.web.json_response(
            {"error": f"TOML format error: {exc}"}, status=400
        )
    path = _main_config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(raw_content, encoding="utf-8")
        await reload_config()
    except Exception as exc:
        return aiohttp.web.json_response({"error": str(exc)}, status=500)
    return aiohttp.web.json_response(
        {"status": "ok", "message": "main_config.toml saved and reloaded"},
    )
