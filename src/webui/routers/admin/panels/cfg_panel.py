"""
configpanel 模块。

本文件为 Provider-Evo 项目标准模块，使用以下约定：

- 模块路径：provider-core.src.webui.routers.admin.panels.configpanel
- 文件名：configpanel.py
- 父包：provider-core/src/webui/routers/admin/panels

职责：

    作为 provider / 核心子系统的标准模块入口；
    通常被 ``plugin.py`` 或上层 ``client.py`` 通过显式 import 使用。

对外接口：

    本模块的 ``__all__`` 列出对外可导入的符号集合；其他内部符号
    可能在重构中调整，调用方应只依赖 ``__all__`` 暴露的稳定 API。

集成：

    - SDK 入口：``plugin.py`` 中 ``create_plugin()`` 引用本模块以构造 platform adapter。
    - 入口路由：``provider-core/src/routes/openai`` 通过 ``from src.core...`` 间接使用。
    - 测试：本目录下的 ``tests/`` 子目录覆盖本模块的核心逻辑。

依赖：

    - 仅依赖 ``provider-sdk`` 与 Python 3.8+ 标准库；不引入第三方 HTTP 库。
    - 不直接读环境变量；所有配置走 ``config/main_config.toml``。

修改指引：

    - 调整本模块时同步更新 ``docs-src/plugins/<name>.md`` 与对应 ``tests/``。
    - 保持单文件 200-400 行；超长请拆为子包并通过 ``__init__.py`` 重新导出。
    - 严禁放置 placeholder / 兜底 / 伪装通过的代码（见 ``AGENTS.md`` Hard Constraints）。
"""


from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Dict

import aiohttp.web

from src.foundation.paths import config_dir
from src.webui.data.services.schema.panel_schema import WEBUI_CONFIG_PANEL_SCHEMA

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
