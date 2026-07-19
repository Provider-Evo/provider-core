"""
config_panel 模块。

本文件为 Provider-Evo 项目标准模块，使用以下约定：

- 模块路径：provider-core.src.webui.routers.admin.panels.config_panel
- 文件名：config_panel.py
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
        return aiohttp.web.json_response({"error": "config body must be an object"}, status=400)
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
        return aiohttp.web.json_response({"error": "body must be an object"}, status=400)
    raw_content = payload.get("raw_content")
    if not isinstance(raw_content, str):
        return aiohttp.web.json_response({"error": "raw_content must be a string"}, status=400)
    try:
        _parse_toml_text(raw_content)
    except Exception as exc:
        return aiohttp.web.json_response({"error": f"TOML format error: {exc}"}, status=400)
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

# =======================================================================
# 相关模块
# =======================================================================
#
# 同包内协同模块通过 ``from .X import Y`` 重导出，外部调用方无需感知包内布局。
# 若需新增协同模块，请将对应 ``.py`` 文件放在本模块同级目录，并在末尾追加重导出。
#
# 设计原则：
#   1. 每个文件只承担一个明确的职责（单一职责原则）。
#   2. 跨文件依赖只通过显式 import 表达；避免隐式全局状态。
#   3. 公共 API 集中在 ``__all__``；私有符号以下划线开头。
#   4. 模块 docstring 描述用途、依赖、修改指引，作为运行时自描述文档。
#
# 错误处理：
#   - 错误一律 raise，不在底层吞掉（见 ``AGENTS.md`` Hard Constraints）。
#   - 上层 ``plugin.py`` / ``client.py`` 统一处理重试与 fallback。
#
# 测试：
#   - ``tests/`` 子目录覆盖本模块的所有公共函数。
#   - 覆盖率门禁为 90%（见 ``pyproject.toml``）。
#
# 文档：
#   - 用户文档位于 ``docs-src/plugins/``。
#   - 架构决策写入 ``PROJECT_DECISIONS.md``。
#
# 重构策略：
#   - 单文件超过 400 行时，提取子模块并通过 ``__init__.py`` 重导出。
#   - 跨多个 Provider 共享的逻辑抽取至 ``src/core/``；本文件不重复实现。
#
# 兼容：
#   - 旧路径 ``from .module import *`` 仍可用（见 ``__all__``）。
#   - 删除本文件前请先在 ``plugin.py`` 中确认无引用。
#
# 验证：
#   - 修改后运行 ``python -m py_compile`` 确认语法。
#   - 运行 ``pytest tests/`` 确认行为。
#   - 运行 ``python .claude/scripts/check_dir_limit.py`` 确认行数约束。
