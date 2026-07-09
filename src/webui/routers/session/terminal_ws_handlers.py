from __future__ import annotations

"""WebUI 终端 WebSocket 消息处理辅助函数。"""

from typing import Any, Dict, List, Optional, Tuple

import aiohttp.web

from src.core.server.infra.terminal_sessions import TerminalSessionStore
from src.logger import get_logger
from src.webui.routers.session.terminal_session import (
    TerminalSession,
    resolve_cwd,
    shell_cd_command,
)

logger = get_logger(__name__)


async def _send_existing_sessions(
    ws: aiohttp.web.WebSocketResponse,
    registry: Dict[str, TerminalSession],
) -> None:
    """向新连接客户端推送已有会话列表。"""
    existing: List[Dict[str, Any]] = []
    for sid, sess in registry.items():
        existing.append({
            "session_id": sid,
            "kind": sess.kind,
            "alive": sess.alive,
            "name": sess.name,
        })
    if not existing:
        return
    try:
        await ws.send_json({"type": "existing_sessions", "sessions": existing})
    except (ConnectionError, RuntimeError):
        logger.debug("Failed to send existing sessions list", exc_info=True)
    except Exception:
        logger.warning("Unexpected error sending existing sessions list", exc_info=True)


def _terminal_mode(session: TerminalSession, kind: str) -> str:
    """推断终端模式标识（conpty 或 pipe）。"""
    if kind == "ssh":
        return "conpty"
    terminal = session._terminal
    if terminal and getattr(terminal, "_conpty", None) is not None:
        return "conpty"
    return "pipe"


async def _attach_readonly_session(
    ws: aiohttp.web.WebSocketResponse,
    session: TerminalSession,
    session_id: str,
) -> None:
    """挂接只读恢复会话并推送离线输出。"""
    session.attach_client(ws)
    await ws.send_json({"type": "ready", "session_id": session_id})
    await ws.send_json({"type": "mode", "mode": "pipe"})
    if session._store:
        offline = session._store.consume_offline_output(session_id)
        if offline:
            await ws.send_json({"type": "output", "data": offline})
    await ws.send_json({"type": "exit", "code": -1})


async def _attach_live_session(
    ws: aiohttp.web.WebSocketResponse,
    session: TerminalSession,
    session_id: str,
    cols: int,
    rows: int,
) -> None:
    """挂接可交互会话并刷新终端尺寸。"""
    buffered = session.attach_client(ws)
    await ws.send_json({"type": "ready", "session_id": session_id})
    await ws.send_json({"type": "mode", "mode": _terminal_mode(session, session.kind)})
    if buffered:
        await ws.send_json({"type": "output", "data": buffered})
    await session.resize(cols, rows)


async def _start_new_session(
    ws: aiohttp.web.WebSocketResponse,
    session_id: str,
    payload: Dict[str, Any],
    registry: Dict[str, TerminalSession],
    store: TerminalSessionStore,
) -> Tuple[Optional[TerminalSession], bool]:
    """创建新终端会话；失败时向客户端返回错误。"""
    kind = payload.get("kind", "local")
    cols = int(payload.get("cols", 80))
    rows = int(payload.get("rows", 24))
    tab_name = payload.get("name")

    existing_session = registry.get(session_id)
    if existing_session:
        registry.pop(session_id, None)

    session = TerminalSession(session_id, kind)
    session._store = store
    session.name = tab_name
    registry[session_id] = session

    if kind == "ssh":
        ok = await session.start_ssh(
            host=payload.get("host", ""),
            port=int(payload.get("port", 22)),
            username=payload.get("username", ""),
            password=payload.get("password", ""),
            key_data=payload.get("key_data", ""),
            cols=cols,
            rows=rows,
        )
    else:
        ok = await session.start_local(cols, rows)

    if not ok:
        if kind == "ssh":
            message = (
                "Failed to start SSH terminal. Check connection settings "
                "and that the remote host is reachable."
            )
        else:
            message = (
                "Failed to start local terminal. Check that a shell is "
                "available and PTY is supported."
            )
        await ws.send_json({"type": "error", "message": message})
        registry.pop(session_id, None)
        return None, False

    buffered = session.attach_client(ws)
    await ws.send_json({"type": "ready", "session_id": session_id})
    await ws.send_json({"type": "mode", "mode": _terminal_mode(session, kind)})
    if buffered:
        await ws.send_json({"type": "output", "data": buffered})
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
    """处理 init 类型 WebSocket 消息。"""
    cols = int(payload.get("cols", 80))
    rows = int(payload.get("rows", 24))
    existing_session = registry.get(session_id)

    if existing_session and existing_session.alive and not existing_session.reattachable:
        await _attach_readonly_session(ws, existing_session, session_id)
        return existing_session, True

    if existing_session and existing_session.alive:
        await _attach_live_session(ws, existing_session, session_id, cols, rows)
        return existing_session, True

    return await _start_new_session(ws, session_id, payload, registry, store)


async def _dispatch_session_message(
    ws: aiohttp.web.WebSocketResponse,
    session: TerminalSession,
    msg_type: str,
    payload: Dict[str, Any],
) -> bool:
    """处理需已绑定 session 的消息；返回 False 表示会话已关闭。"""
    cols = int(payload.get("cols", 80))
    rows = int(payload.get("rows", 24))
    if msg_type == "input":
        data = payload.get("data", "")
        if data:
            await session.write(data)
        return True
    if msg_type == "resize":
        await session.resize(cols, rows)
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
            await ws.send_json({"type": "error", "message": "Failed to restart terminal"})
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
    """处理单条终端 WebSocket 消息。"""
    msg_type = payload.get("type")
    if msg_type == "init":
        return await handle_init_message(ws, payload, session_id, registry, store)
    if msg_type == "ping":
        await ws.send_json({"type": "pong"})
        return session, initialized
    if session and not await _dispatch_session_message(ws, session, msg_type, payload):
        return None, False
    return session, initialized
