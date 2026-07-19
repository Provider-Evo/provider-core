"""WebUI 插件配置读写 API。"""
from __future__ import annotations

import json
from typing import Any, Dict

import aiohttp.web

from src.foundation.logger import get_logger
from src.webui.routers.admin.plugins.plugin_support import find_plugin_path_by_id

__all__ = [
    "plugins_config_bundle",
    "plugins_config_get",
    "plugins_config_put",
    "plugins_config_reset",
]

logger = get_logger(__name__)


def _read_plugin_config_files(plugin_path: Any) -> "tuple[Dict[str, Any], Dict[str, Any], str]":
    config_path = plugin_path / "config.toml"
    config: Dict[str, Any] = {}
    if config_path.is_file():
        try:
            import tomlkit

            config = dict(tomlkit.loads(config_path.read_text(encoding="utf-8")))
        except Exception:
            config = {}

    schema: Dict[str, Any] = {}
    schema_path = plugin_path / "config_schema.json"
    if schema_path.is_file():
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    raw_text = config_path.read_text(encoding="utf-8") if config_path.is_file() else ""
    return config, schema, raw_text


def _default_for_schema_field(field: Dict[str, Any]) -> Any:
    if "default" in field:
        return field["default"]
    ftype = field.get("type")
    if ftype == "object":
        nested = _defaults_from_schema(field)
        return nested if nested else None
    if ftype == "boolean":
        return False
    if ftype in ("integer", "number"):
        return 0
    if ftype == "string":
        return ""
    return None


def _defaults_from_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    if not schema or schema.get("type") != "object":
        return {}
    props = schema.get("properties") or {}
    result: Dict[str, Any] = {}
    for key, field in props.items():
        if not isinstance(field, dict):
            continue
        value = _default_for_schema_field(field)
        if value is not None:
            result[key] = value
    return result


async def plugins_config_get(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/admin/plugins/config/{plugin_id} — 获取插件配置。"""
    plugin_id = request.match_info.get("plugin_id", "")
    plugin_path = find_plugin_path_by_id(plugin_id)
    if not plugin_path:
        return aiohttp.web.json_response({"error": "plugin not found"}, status=404)

    config, schema, raw_text = _read_plugin_config_files(plugin_path)

    return aiohttp.web.json_response({
        "plugin_id": plugin_id,
        "config": config,
        "schema": schema,
        "raw": raw_text,
    })


async def plugins_config_bundle(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/admin/plugins/config/{plugin_id}/bundle — 配置页初始化数据。"""
    plugin_id = request.match_info.get("plugin_id", "")
    plugin_path = find_plugin_path_by_id(plugin_id)
    if not plugin_path:
        return aiohttp.web.json_response({"success": False, "error": "plugin not found"}, status=404)

    config, schema, raw_text = _read_plugin_config_files(plugin_path)
    config_path = plugin_path / "config.toml"
    message = ""
    if not config_path.is_file() and schema:
        config = _defaults_from_schema(schema)
        message = "配置文件不存在，已返回默认配置"

    return aiohttp.web.json_response({
        "success": True,
        "plugin_id": plugin_id,
        "schema": schema,
        "config": config,
        "raw_config": raw_text,
        "message": message,
    })


async def plugins_config_reset(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/admin/plugins/config/{plugin_id}/reset — 重置插件配置。"""
    plugin_id = request.match_info.get("plugin_id", "")
    plugin_path = find_plugin_path_by_id(plugin_id)
    if not plugin_path:
        return aiohttp.web.json_response({"success": False, "error": "plugin not found"}, status=404)

    config_path = plugin_path / "config.toml"
    _, schema, _ = _read_plugin_config_files(plugin_path)
    defaults = _defaults_from_schema(schema) if schema else {}

    try:
        import tomlkit

        if defaults:
            config_path.write_text(tomlkit.dumps(defaults), encoding="utf-8")
        elif config_path.is_file():
            config_path.unlink()
    except Exception as exc:
        logger.error("插件配置重置失败: %s", exc)
        return aiohttp.web.json_response({"success": False, "error": str(exc)}, status=500)

    return aiohttp.web.json_response({
        "success": True,
        "config": defaults,
        "raw_config": config_path.read_text(encoding="utf-8") if config_path.is_file() else "",
    })


def _merge_config(base: dict, patch: dict) -> dict:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge_config(base[key], value)
        else:
            base[key] = value
    return base


async def plugins_config_put(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """PUT /v1/admin/plugins/config/{plugin_id} — 更新插件配置。"""
    plugin_id = request.match_info.get("plugin_id", "")
    plugin_path = find_plugin_path_by_id(plugin_id)
    if not plugin_path:
        return aiohttp.web.json_response({"error": "plugin not found"}, status=404)

    try:
        body = await request.json()
    except Exception:
        return aiohttp.web.json_response({"error": "invalid json"}, status=400)

    config_path = plugin_path / "config.toml"
    if "raw" in body and isinstance(body.get("raw"), str):
        config_path.write_text(body["raw"], encoding="utf-8")
        return aiohttp.web.json_response({"status": "ok"})

    config_data = body.get("config", {})
    if not isinstance(config_data, dict):
        return aiohttp.web.json_response({"error": "config must be dict"}, status=400)

    try:
        import tomlkit

        if config_path.is_file():
            existing = tomlkit.loads(config_path.read_text(encoding="utf-8"))
        else:
            existing = tomlkit.document()

        _merge_config(existing, config_data)
        config_path.write_text(tomlkit.dumps(existing), encoding="utf-8")
    except Exception as exc:
        logger.error("插件配置保存失败: %s", exc)
        return aiohttp.web.json_response({"error": str(exc)}, status=500)

    return aiohttp.web.json_response({"status": "ok"})
