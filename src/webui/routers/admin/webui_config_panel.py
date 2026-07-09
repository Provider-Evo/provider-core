"""WebUI 便携配置面板 API — 读写 config/webui_config.toml。"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Dict

import aiohttp.web

from src.foundation.paths import config_dir
from src.webui.services.config_panel_schema import WEBUI_CONFIG_PANEL_SCHEMA

__all__ = [
    "webui_config_get",
    "webui_config_put",
    "webui_config_reload",
    "webui_config_schema_get",
    "webui_config_raw_get",
    "webui_config_raw_put",
]


def _webui_config_path() -> Path:
    return config_dir() / "webui_config.toml"


def _parse_toml_text(raw_content: str) -> Dict[str, Any]:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

    data = tomllib.load(io.BytesIO(raw_content.encode("utf-8")))
    if not isinstance(data, dict):
        raise ValueError("root must be a TOML table")
    return data


def _load_webui_config_dict() -> Dict[str, Any]:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

    path = _webui_config_path()
    if not path.is_file():
        return {}
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    return data if isinstance(data, dict) else {}


def _write_webui_config_dict(body: Dict[str, Any]) -> None:
    path = _webui_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import tomlkit
    except ImportError:
        tomlkit = None  # type: ignore[assignment]

    if tomlkit is not None:
        with open(path, "w", encoding="utf-8") as fh:
            tomlkit.dump(body, fh)
        return

    lines: list[str] = []
    for key, value in body.items():
        if isinstance(value, bool):
            lines.append(f"{key} = {'true' if value else 'false'}")
        elif isinstance(value, (int, float)):
            lines.append(f"{key} = {value}")
        elif isinstance(value, str):
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{key} = "{escaped}"')
        else:
            import json

            lines.append(f"{key} = {json.dumps(value, ensure_ascii=False)}")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


async def webui_config_get(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/webui/config — 返回 webui_config.toml。"""
    del request
    try:
        return aiohttp.web.json_response(_load_webui_config_dict())
    except Exception as exc:
        return aiohttp.web.json_response({"error": str(exc)}, status=500)


async def webui_config_put(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """PUT /v1/webui/config — 写入 webui_config.toml。"""
    try:
        payload = await request.json()
    except Exception:
        return aiohttp.web.json_response({"error": "invalid JSON body"}, status=400)
    if not isinstance(payload, dict):
        return aiohttp.web.json_response({"error": "config body must be an object"}, status=400)
    try:
        _write_webui_config_dict(payload)
    except Exception as exc:
        return aiohttp.web.json_response({"error": str(exc)}, status=500)
    return aiohttp.web.json_response(
        {"status": "ok", "message": "webui_config.toml saved"},
    )


async def webui_config_reload(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/webui/config/reload — 从磁盘重新加载 webui_config.toml。"""
    del request
    try:
        data = _load_webui_config_dict()
    except Exception as exc:
        return aiohttp.web.json_response({"error": str(exc)}, status=500)
    return aiohttp.web.json_response(
        {"status": "ok", "message": "webui_config.toml reloaded", "data": data},
    )


async def webui_config_schema_get(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/admin/webui/config/schema — WebUI 便携配置 schema。"""
    del request
    return aiohttp.web.json_response(WEBUI_CONFIG_PANEL_SCHEMA)


async def webui_config_raw_get(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/webui/config/raw — 返回 webui_config.toml 原始 TOML 文本。"""
    del request
    path = _webui_config_path()
    if not path.is_file():
        return aiohttp.web.json_response({"success": True, "content": ""})
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:
        return aiohttp.web.json_response({"error": str(exc)}, status=500)
    return aiohttp.web.json_response({"success": True, "content": content})


async def webui_config_raw_put(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/webui/config/raw — 写入 webui_config.toml 原始 TOML。"""
    try:
        payload = await request.json()
    except Exception:
        return aiohttp.web.json_response({"error": "invalid JSON body"}, status=400)
    if not isinstance(payload, dict):
        return aiohttp.web.json_response({"error": "body must be an object"}, status=400)
    raw_content = payload.get("raw_content")
    if not isinstance(raw_content, str):
        return aiohttp.web.json_response({"error": "raw_content must be a string"}, status=400)
    try:
        _parse_toml_text(raw_content)
    except Exception as exc:
        return aiohttp.web.json_response({"error": f"TOML format error: {exc}"}, status=400)
    path = _webui_config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(raw_content, encoding="utf-8")
    except Exception as exc:
        return aiohttp.web.json_response({"error": str(exc)}, status=500)
    return aiohttp.web.json_response(
        {"status": "ok", "message": "webui_config.toml saved"},
    )
