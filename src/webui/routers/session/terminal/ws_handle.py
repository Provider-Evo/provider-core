from __future__ import annotations

"""WebUI 终端 WebSocket 消息处理辅助函数（协议 v2）。"""

from typing import Any, Dict, List, Optional, Tuple

import aiohttp.web

from src.core.server.terminal.sess import TerminalSessionStore
from src.core.server.terminal.ssh_vault import get_ssh_vault
from src.foundation.logger import get_logger
from src.webui.routers.session.terminal.term_proto import PROTOCOL_VERSION
from src.webui.routers.session.terminal.term_sess import (
    TerminalSession,
    resolve_cwd,
    resolve_ssh_from_payload,
    shell_cd_command,
)

logger = get_logger(__name__)

_SSH_START_FALLBACK = (
    "Failed to start SSH terminal. Check connection settings "
    "and that the remote host is reachable."
)
_LOCAL_START_FALLBACK = (
    "Failed to start local terminal. Check that a shell is "
    "available and PTY is supported."
)
_RESTART_FALLBACK = "Failed to restart terminal"


def _start_error_message(session: TerminalSession, kind: str) -> str:
    detail = session.last_start_error
    if detail:
        return detail
    if kind == "ssh":
        return _SSH_START_FALLBACK
    return _LOCAL_START_FALLBACK


async def _send_existing_sessions(
    ws: aiohttp.web.WebSocketResponse,
    registry: Dict[str, TerminalSession],
) -> None:
    existing: List[Dict[str, Any]] = []
    for sid, sess in registry.items():
        existing.append({
            "session_id": sid,
            "kind": sess.kind,
            "alive": sess.alive,
            "name": sess.name,
            "readonly": sess.readonly,
        })
    if not existing:
        return
    try:
        await ws.send_json({"type": "existing_sessions", "sessions": existing})
    except (ConnectionError, RuntimeError):
        logger.debug("Failed to send existing sessions list", exc_info=True)


def _terminal_mode(session: TerminalSession, kind: str) -> str:
    if kind == "ssh":
        return "conpty"
    terminal = session._terminal
    if terminal and getattr(terminal, "_conpty", None) is not None:
        return "conpty"
    if terminal and session.__class__.__name__:
        backend = getattr(terminal, "kind", "")
        if backend == "tmux":
            return "tmux"
    return "pipe"


async def _send_attached(
    ws: aiohttp.web.WebSocketResponse,
    session: TerminalSession,
    session_id: str,
    attach_info: Dict[str, Any],
) -> None:
    await ws.send_json({"type": "ready", "session_id": session_id})
    await ws.send_json({"type": "mode", "mode": _terminal_mode(session, session.kind)})
    await ws.send_json({
        "type": "attached",
        "session_id": session_id,
        "protocol_version": attach_info.get("protocol_version", PROTOCOL_VERSION),
        "mode": attach_info.get("mode", "readonly"),
        "replay_from_seq": attach_info.get("replay_from_seq", 0),
        "head_seq": attach_info.get("head_seq", 0),
        "writable": attach_info.get("writable", False),
    })


async def _attach_readonly_session(
    ws: aiohttp.web.WebSocketResponse,
    session: TerminalSession,
    session_id: str,
    since_seq: int,
) -> None:
    attach_info = session.attach_client(ws, since_seq=since_seq, writable=False)
    await _send_attached(ws, session, session_id, attach_info)
    if not session.alive:
        await ws.send_json({"type": "exit", "code": -1})


async def _attach_live_session(
    ws: aiohttp.web.WebSocketResponse,
    session: TerminalSession,
    session_id: str,
    cols: int,
    rows: int,
    since_seq: int,
) -> None:
    attach_info = session.attach_client(ws, since_seq=since_seq, writable=True)
    await _send_attached(ws, session, session_id, attach_info)
    await session.resize(cols, rows)


async def _start_session_backend(
    session: TerminalSession,
    kind: str,
    payload: Dict[str, Any],
    cols: int,
    rows: int,
) -> bool:
    """根据会话类型启动本地或 SSH 后端进程。"""
    if kind != "ssh":
        return await session.start_local(cols, rows)

    ssh_fields = resolve_ssh_from_payload(payload)
    if payload.get("save_connection"):
        cid = get_ssh_vault().upsert(
            host=ssh_fields["host"],
            port=ssh_fields["port"],
            username=ssh_fields["username"],
            password=ssh_fields.get("password", ""),
            key_data=ssh_fields.get("key_data", ""),
            name=str(payload.get("name") or ssh_fields.get("name") or ""),
            connection_id=ssh_fields.get("connection_id"),
        )
        ssh_fields["connection_id"] = cid
    return await session.start_ssh(
        host=ssh_fields["host"],
        port=ssh_fields["port"],
        username=ssh_fields["username"],
        password=ssh_fields.get("password", ""),
        key_data=ssh_fields.get("key_data", ""),
        cols=cols,
        rows=rows,
        connection_id=ssh_fields.get("connection_id"),
        trust_host_key=bool(payload.get("trust_host_key", True)),
    )


async def _start_new_session(
    ws: aiohttp.web.WebSocketResponse,
    session_id: str,
    payload: Dict[str, Any],
    registry: Dict[str, TerminalSession],
    store: TerminalSessionStore,
) -> Tuple[Optional[TerminalSession], bool]:
    kind = payload.get("kind", "local")
    cols = int(payload.get("cols", 80))
    rows = int(payload.get("rows", 24))
    tab_name = payload.get("name")
    since_seq = int(payload.get("since_seq", 0))

    existing_session = registry.get(session_id)
    if existing_session:
        registry.pop(session_id, None)

    session = TerminalSession(session_id, kind)
    session._store = store
    session.name = tab_name
    registry[session_id] = session

    ok = await _start_session_backend(session, kind, payload, cols, rows)

    if not ok:
        message = _start_error_message(session, kind)
        await ws.send_json({"type": "error", "message": message})
        registry.pop(session_id, None)
        return None, False

    attach_info = session.attach_client(ws, since_seq=since_seq, writable=True)
    await _send_attached(ws, session, session_id, attach_info)

    cwd_path = resolve_cwd(payload.get("cwd"))
    if cwd_path and kind == "local":
        await session.write(shell_cd_command(str(cwd_path)))
        if session._store:
            session._store.save(session_id=session_id, cwd=str(cwd_path))
    return session, True


async def handle_init_message(
    ws: aiohttp.web.WebSocketResponse,
    payload: Dict[str, Any],
    session_id: str,
    registry: Dict[str, TerminalSession],
    store: TerminalSessionStore,
) -> Tuple[Optional[TerminalSession], bool]:
    cols = int(payload.get("cols", 80))
    rows = int(payload.get("rows", 24))
    since_seq = int(payload.get("since_seq", 0))
    existing_session = registry.get(session_id)

    if existing_session and existing_session.alive and not existing_session.reattachable:
        await _attach_readonly_session(ws, existing_session, session_id, since_seq)
        return existing_session, True

    if existing_session and existing_session.alive:
        await _attach_live_session(
            ws, existing_session, session_id, cols, rows, since_seq
        )
        return existing_session, True

    if existing_session and not existing_session.alive:
        await _attach_readonly_session(ws, existing_session, session_id, since_seq)
        return existing_session, True

    return await _start_new_session(ws, session_id, payload, registry, store)


async def _dispatch_session_message(
    ws: aiohttp.web.WebSocketResponse,
    session: TerminalSession,
    session_id: str,
    msg_type: str,
    payload: Dict[str, Any],
) -> bool:
    cols = int(payload.get("cols", 80))
    rows = int(payload.get("rows", 24))
    if msg_type == "input":
        data = payload.get("data", "")
        if data and session.can_client_write(ws):
            await session.write(data)
        return True
    if msg_type == "resize":
        await session.resize(cols, rows)
        return True
    if msg_type == "pause":
        await session.set_client_backpressure(ws, paused=True)
        return True
    if msg_type == "resume":
        await session.set_client_backpressure(ws, paused=False)
        return True
    if msg_type == "close_session":
        await session.kill()
        return False
    if msg_type == "clear":
        await session.clear()
        return True
    if msg_type == "restart":
        ok = await session.restart(cols, rows)
        if not ok:
            message = session.last_start_error or _RESTART_FALLBACK
            await ws.send_json({"type": "error", "message": message})
        else:
            attach_info = session.attach_client(ws, since_seq=0, writable=True)
            await _send_attached(ws, session, session_id, attach_info)
        return True
    return True


async def handle_terminal_ws_message(
    ws: aiohttp.web.WebSocketResponse,
    payload: Dict[str, Any],
    session: Optional[TerminalSession],
    session_id: str,
    registry: Dict[str, TerminalSession],
    store: TerminalSessionStore,
    initialized: bool,
) -> Tuple[Optional[TerminalSession], bool]:
    msg_type = payload.get("type")
    if msg_type == "init":
        return await handle_init_message(ws, payload, session_id, registry, store)
    if msg_type == "ping":
        await ws.send_json({"type": "pong"})
        return session, initialized
    if session and not await _dispatch_session_message(
        ws, session, session_id, msg_type, payload
    ):
        return None, False
    return session, initialized


async def handle_terminal_binary_input(
    ws: aiohttp.web.WebSocketResponse,
    session: Optional[TerminalSession],
    data: bytes,
) -> None:
    if session and session.can_client_write(ws):
        await session.write_bytes(data)
