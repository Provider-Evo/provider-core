"""
terminal 模块。

本文件为 Provider-Evo 项目标准模块，使用以下约定：

- 模块路径：provider-core.src.webui.routers.session.terminal.terminal
- 文件名：terminal.py
- 父包：provider-core/src/webui/routers/session/terminal

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


import json
import uuid
from typing import Optional

import aiohttp.web
from echotools.terminal import LocalTerminal, SSHTerminal

from src.core.server.terminal.common_cmds import get_commands_store
from src.core.server.terminal.session_audit import get_audit_store
from src.core.server.terminal.sess import get_terminal_store
from src.core.server.terminal.ssh_vault import get_ssh_vault
from src.foundation.config import get_config, write_config
from src.foundation.logger import get_logger
from src.webui.routers.admin.panels.config_panel import _load_main_config_dict
from src.foundation.paths import config_dir
from src.webui.routers.session.terminal.term_sess import (
    TerminalSession,
    TerminalSession as _TerminalSession,
    list_sessions,
    recover_sessions,
    sessions_registry,
)
from src.webui.routers.session.terminal.ws_handle import (
    _send_existing_sessions,
    handle_terminal_binary_input,
    handle_terminal_ws_message,
)

logger = get_logger(__name__)

__all__ = [
    "terminal_ws",
    "terminal_sessions_api",
    "terminal_ssh_connections_api",
    "terminal_audit_api",
    "terminal_audit_detail_api",
    "terminal_audit_config_api",
    "terminal_commands_api",
    "terminal_commands_export_api",
    "terminal_commands_import_api",
    "recover_sessions",
    "_TerminalSession",
    "LocalTerminal",
    "SSHTerminal",
]

_sessions = sessions_registry()


async def terminal_ws(request: aiohttp.web.Request) -> aiohttp.web.WebSocketResponse:
    """WebSocket 端点 ``/v1/webui/ws/terminal/{session_id}``。"""
    session_id = request.match_info.get("session_id", str(uuid.uuid4()))
    ws = aiohttp.web.WebSocketResponse(heartbeat=30.0, compress=False)
    await ws.prepare(request)

    store = get_terminal_store()
    session: Optional[TerminalSession] = None
    initialized = False

    try:
        await _send_existing_sessions(ws, _sessions)
        async for msg in ws:
            if msg.type in (
                aiohttp.WSMsgType.CLOSE,
                aiohttp.WSMsgType.CLOSED,
                aiohttp.WSMsgType.ERROR,
            ):
                break
            try:
                if msg.type == aiohttp.WSMsgType.BINARY:
                    await handle_terminal_binary_input(ws, session, msg.data)
                    initialized = initialized or session is not None
                    continue
                if msg.type != aiohttp.WSMsgType.TEXT:
                    continue
                try:
                    payload = json.loads(msg.data)
                except (json.JSONDecodeError, TypeError):
                    continue
                session, initialized = await handle_terminal_ws_message(
                    ws, payload, session, session_id, _sessions, store, initialized
                )
            except (ConnectionError, RuntimeError):
                break
    finally:
        if session and initialized:
            session.detach_client(ws)
            logger.debug(
                "WS disconnected from session %s (%d clients remaining)",
                session_id,
                len(session._clients),
            )
    return ws


async def terminal_sessions_api(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET ``/v1/webui/terminal/sessions`` — 列出活动终端会话。"""
    store = get_terminal_store()
    result = []
    for sid, sess in _sessions.items():
        result.append({
            "session_id": sid,
            "kind": sess.kind,
            "alive": sess.alive,
            "readonly": sess.readonly,
            "clients": len(sess._clients),
            "name": sess.name,
        })
    active_ids = set(_sessions.keys())
    for meta in store.list_all():
        sid = meta.get("session_id")
        if sid and sid not in active_ids:
            result.append({
                "session_id": sid,
                "kind": meta.get("kind", "local"),
                "alive": meta.get("status") == "alive",
                "readonly": True,
                "clients": 0,
                "name": meta.get("name"),
            })
    return aiohttp.web.json_response(result)


async def terminal_ssh_connections_api(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """GET/POST/DELETE ``/v1/webui/terminal/ssh-connections`` — SSH vault。"""
    vault = get_ssh_vault()
    if request.method == "GET":
        return aiohttp.web.json_response({"connections": vault.list_public()})
    if request.method == "POST":
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return aiohttp.web.json_response({"error": "invalid json"}, status=400)
        cid = vault.upsert(
            host=str(body.get("host", "")),
            port=int(body.get("port", 22)),
            username=str(body.get("username", "")),
            password=str(body.get("password", "")),
            key_data=str(body.get("key_data", "")),
            name=body.get("name"),
            connection_id=body.get("connection_id"),
        )
        return aiohttp.web.json_response({"connection_id": cid})
    if request.method == "DELETE":
        cid = request.match_info.get("connection_id") or request.query.get("id")
        if not cid:
            return aiohttp.web.json_response({"error": "missing id"}, status=400)
        vault.delete(str(cid))
        return aiohttp.web.json_response({"ok": True})
    return aiohttp.web.json_response({"error": "method not allowed"}, status=405)


async def terminal_audit_api(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET ``/v1/webui/terminal/audit`` — 分页列出终端会话审计日志。"""
    store = get_audit_store()
    try:
        page = int(request.query.get("page", 1))
    except ValueError:
        page = 1
    try:
        page_size = int(request.query.get("page_size", 20))
    except ValueError:
        page_size = 20
    return aiohttp.web.json_response(store.list_page(page, page_size))


async def terminal_audit_detail_api(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET/DELETE ``/v1/webui/terminal/audit/{session_id}`` — 审计详情/删除。"""
    session_id = request.match_info.get("session_id", "")
    store = get_audit_store()
    if request.method == "GET":
        entry = store.get(session_id)
        if entry is None:
            return aiohttp.web.json_response({"error": "not found"}, status=404)
        result = dict(entry)
        result["output"] = get_terminal_store().get_offline_output(session_id)
        return aiohttp.web.json_response(result)
    if request.method == "DELETE":
        ok = store.delete(session_id)
        if not ok:
            return aiohttp.web.json_response({"error": "not found"}, status=404)
        return aiohttp.web.json_response({"ok": True})
    return aiohttp.web.json_response({"error": "method not allowed"}, status=405)


async def terminal_audit_config_api(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET/POST ``/v1/webui/terminal/audit/config`` — 审计开关。"""
    if request.method == "GET":
        return aiohttp.web.json_response(
            {"audit_enabled": get_config().terminal.audit_enabled}
        )
    if request.method == "POST":
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return aiohttp.web.json_response({"error": "invalid json"}, status=400)
        enabled = bool(body.get("audit_enabled"))
        current = _load_main_config_dict()
        current.setdefault("terminal", {})["audit_enabled"] = enabled
        ok = await write_config(current)
        if not ok:
            return aiohttp.web.json_response({"error": "write failed"}, status=500)
        get_config().terminal.audit_enabled = enabled
        return aiohttp.web.json_response({"audit_enabled": enabled})
    return aiohttp.web.json_response({"error": "method not allowed"}, status=405)


async def terminal_commands_api(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET/POST/DELETE ``/v1/webui/terminal/commands`` — 常用命令。"""
    store = get_commands_store()
    if request.method == "GET":
        return aiohttp.web.json_response({"commands": store.list_all()})
    if request.method == "POST":
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return aiohttp.web.json_response({"error": "invalid json"}, status=400)
        cid = store.upsert(
            name=str(body.get("name", "")),
            command=str(body.get("command", "")),
            auto_enter=bool(body.get("auto_enter", False)),
            command_id=body.get("command_id"),
        )
        return aiohttp.web.json_response({"id": cid})
    if request.method == "DELETE":
        cid = request.match_info.get("command_id") or request.query.get("id")
        if not cid:
            try:
                body = await request.json()
                cid = body.get("command_id")
            except json.JSONDecodeError:
                cid = None
        if not cid:
            return aiohttp.web.json_response({"error": "missing id"}, status=400)
        ok = store.delete(str(cid))
        if not ok:
            return aiohttp.web.json_response({"error": "not found"}, status=404)
        return aiohttp.web.json_response({"ok": True})
    return aiohttp.web.json_response({"error": "method not allowed"}, status=405)


async def terminal_commands_export_api(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """GET ``/v1/webui/terminal/commands/export`` — 导出常用命令。"""
    del request
    return aiohttp.web.json_response(get_commands_store().export_all())


async def terminal_commands_import_api(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """POST ``/v1/webui/terminal/commands/import`` — 导入常用命令。"""
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return aiohttp.web.json_response({"error": "invalid json"}, status=400)
    commands = body.get("commands")
    if not isinstance(commands, list):
        return aiohttp.web.json_response({"error": "commands must be a list"}, status=400)
    count = get_commands_store().import_many(commands)
    return aiohttp.web.json_response({"imported": count})

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
