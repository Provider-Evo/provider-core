from __future__ import annotations

"""WebUI 终端 WebSocket 路由 — 仅负责传输层协议。"""

import json
import uuid
from typing import Optional

import aiohttp.web
from echotools.terminal import LocalTerminal, SSHTerminal

from src.core.server.infra.terminal_sessions import get_terminal_store
from src.foundation.logger import get_logger
from src.webui.routers.session.terminal.terminal_session import (
    TerminalSession,
    TerminalSession as _TerminalSession,
    list_sessions,
    recover_sessions,
    sessions_registry,
)
from src.webui.routers.session.terminal.terminal_ws_handlers import (
    _send_existing_sessions,
    handle_terminal_ws_message,
)

logger = get_logger(__name__)

__all__ = [
    "terminal_ws",
    "terminal_sessions_api",
    "recover_sessions",
    "_TerminalSession",
    "LocalTerminal",
    "SSHTerminal",
]

_sessions = sessions_registry()


async def terminal_ws(request: aiohttp.web.Request) -> aiohttp.web.WebSocketResponse:
    """WebSocket 端点 ``/v1/webui/ws/terminal/{session_id}``。"""
    session_id = request.match_info.get("session_id", str(uuid.uuid4()))
    ws = aiohttp.web.WebSocketResponse(heartbeat=30.0)
    await ws.prepare(request)

    store = get_terminal_store()
    session: Optional[TerminalSession] = None
    initialized = False

    try:
        await _send_existing_sessions(ws, _sessions)
        async for msg in ws:
            if msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                break
            if msg.type != aiohttp.WSMsgType.TEXT:
                continue
            try:
                payload = json.loads(msg.data)
            except (json.JSONDecodeError, TypeError):
                continue
            session, initialized = await handle_terminal_ws_message(
                ws, payload, session, session_id, _sessions, store, initialized
            )
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
                "clients": 0,
                "name": meta.get("name"),
            })
    return aiohttp.web.json_response(result)
