
import json
import uuid
from typing import Optional

import aiohttp.web
from echotools.terminal import LocalTerminal, SSHTerminal

from src.core.server.terminal.common_cmds import get_commands_store
from src.core.server.terminal.sess import get_terminal_store
from src.core.server.terminal.session_audit import get_audit_store
from src.core.server.terminal.ssh_vault import get_ssh_vault
from src.foundation.config import get_config, write_config
from src.foundation.logger import get_logger
from src.foundation.paths import config_dir
from src.webui.routers.admin.panels.config_panel import _load_main_config_dict
from src.webui.routers.session.terminal.term_sess import TerminalSession
from src.webui.routers.session.terminal.term_sess import (
    TerminalSession as _TerminalSession,
)
from src.webui.routers.session.terminal.term_sess import (
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
        result.append(
            {
                "session_id": sid,
                "kind": sess.kind,
                "alive": sess.alive,
                "readonly": sess.readonly,
                "clients": len(sess._clients),
                "name": sess.name,
            }
        )
    active_ids = set(_sessions.keys())
    for meta in store.list_all():
        sid = meta.get("session_id")
        if sid and sid not in active_ids:
            result.append(
                {
                    "session_id": sid,
                    "kind": meta.get("kind", "local"),
                    "alive": meta.get("status") == "alive",
                    "readonly": True,
                    "clients": 0,
                    "name": meta.get("name"),
                }
            )
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


async def terminal_audit_detail_api(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
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


async def terminal_audit_config_api(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
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
        return aiohttp.web.json_response(
            {"error": "commands must be a list"}, status=400
        )
    count = get_commands_store().import_many(commands)
    return aiohttp.web.json_response({"imported": count})
