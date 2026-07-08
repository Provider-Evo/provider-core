from __future__ import annotations

"""WebUI Terminal WebSocket router.

Provides local and SSH remote terminal sessions via WebSocket,
using xterm.js on the frontend.

Terminal process management is delegated to ``echotools.terminal``
(``LocalTerminal`` / ``SSHTerminal``).  This module only handles the
WebSocket transport layer via ``_TerminalSession``.

Session lifecycle
-----------------
* **WS connect** -- if a session with the given ID exists, attach the
  new client and deliver buffered offline output; otherwise create a
  new session.
* **WS disconnect** -- detach the client from the session.  If no
  clients remain, the shell process keeps running (output is buffered).
* **close_session message** -- the user explicitly closed the tab.
  Kill the process and destroy the session.
* **Server startup** -- recover surviving sessions from the persistence
  store and notify connecting clients.
"""

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import aiohttp.web
from echotools.terminal import LocalTerminal, SSHTerminal, TerminalCallback

from src.core.terminal_sessions import TerminalSessionStore, get_terminal_store
from src.logger import get_logger

logger = get_logger(__name__)

__all__ = ["terminal_ws", "terminal_sessions_api"]


class _TerminalSession:
    """Server-side session wrapper that manages a terminal process
    and its attached WebSocket clients.

    Supports multi-client: multiple WebSocket connections can attach
    to the same session.  Output is broadcast to all attached clients.
    When no clients remain, the process keeps running and output is
    buffered by the underlying ``LocalTerminal``.
    """

    def __init__(self, session_id: str, kind: str) -> None:
        self.session_id = session_id
        self.kind = kind
        self._terminal: Optional[LocalTerminal | SSHTerminal] = None
        self._clients: Set[aiohttp.web.WebSocketResponse] = set()
        self._store: Optional[TerminalSessionStore] = None
        self.alive: bool = False
        self.name: Optional[str] = None
        self.reattachable: bool = True  # False for recovered sessions that lost PTY handles

    # ------------------------------------------------------------------
    # Start helpers
    # ------------------------------------------------------------------

    async def start_local(self, cols: int = 80, rows: int = 24) -> bool:
        """Create and start a ``LocalTerminal`` session.

        No callback is passed to the constructor -- callbacks are added
        later via ``attach_client()`` to prevent duplicate writers.
        """
        self._terminal = LocalTerminal(self.session_id)
        ok = await self._terminal.start(cols, rows)
        if ok:
            self.alive = True
            # Save session state
            if self._store:
                self._store.save(
                    session_id=self.session_id,
                    pid=self._terminal.pid,
                    cols=cols,
                    rows=rows,
                    kind="local",
                    name=self.name,
                    status="alive",
                )
        return ok

    async def start_ssh(
        self,
        host: str,
        port: int = 22,
        username: str = "",
        password: str = "",
        key_data: str = "",
        cols: int = 80,
        rows: int = 24,
    ) -> bool:
        """Create and start an ``SSHTerminal`` session.

        No callback is passed to the constructor -- callbacks are added
        later via ``attach_client()`` to prevent duplicate writers.
        """
        self._terminal = SSHTerminal(
            self.session_id,
            host=host,
            port=port,
            username=username,
            password=password or None,
            key_data=key_data or None,
        )
        ok = await self._terminal.start(cols, rows)
        if ok:
            self.alive = True
            if self._store:
                self._store.save(
                    session_id=self.session_id,
                    pid=None,
                    cols=cols,
                    rows=rows,
                    kind="ssh",
                    ssh_config={"host": host, "port": port, "username": username},
                    name=self.name,
                    status="alive",
                )
        return ok

    # ------------------------------------------------------------------
    # Client attachment
    # ------------------------------------------------------------------

    def attach_client(self, ws: aiohttp.web.WebSocketResponse) -> Optional[str]:
        """Attach a WebSocket client to this session.

        Returns the buffered offline output (if any) that should be
        sent to the newly attached client.  Returns ``None`` if there
        is no buffered output.

        For non-reattachable sessions (recovered after server restart),
        returns the persisted offline output and marks the session as
        read-only.
        """
        self._clients.add(ws)

        # Non-reattachable session: serve offline output only
        if not self.reattachable:
            if self._store:
                offline = self._store.consume_offline_output(self.session_id)
                return offline if offline else None
            return None

        if self._terminal is not None:
            # Create a callback for this client and attach it
            callback = TerminalCallback(
                on_output=self._broadcast_output,
                on_error=self._broadcast_error,
                on_exit=self._broadcast_exit,
                on_metadata=self._broadcast_metadata,
            )
            buffered = self._terminal.attach(callback)

            # Also save to persist store
            if self._store and buffered:
                self._store.append_output(self.session_id, buffered)
            elif self._store:
                # Check for persisted offline output
                persisted = self._store.get_offline_output(self.session_id)
                if persisted:
                    buffered = persisted
                    self._store.clear_offline_output(self.session_id)

            return buffered if buffered else None
        return None

    def detach_client(self, ws: aiohttp.web.WebSocketResponse) -> None:
        """Detach a WebSocket client from this session.

        If no clients remain, the terminal process keeps running
        (output is buffered by the underlying terminal).
        """
        self._clients.discard(ws)

        if not self._clients and self._terminal is not None:
            # No clients left -- detach the terminal (keep process alive)
            self._terminal.detach()
            logger.info(
                "Session %s: all clients detached, process kept alive",
                self.session_id,
            )

    # ------------------------------------------------------------------
    # Broadcast callbacks (terminal -> all WS clients)
    # ------------------------------------------------------------------

    async def _broadcast_output(self, data: str) -> None:
        """Forward terminal output to all attached WebSocket clients.

        Also append to the persist store for offline recovery.
        """
        # Persist offline output
        if self._store:
            self._store.append_output(self.session_id, data)

        if not self._clients:
            return

        dead_clients = []
        for ws in list(self._clients):
            try:
                if not ws.closed:
                    await ws.send_json({"type": "output", "data": data})
            except Exception:
                dead_clients.append(ws)

        # Clean up dead clients
        for ws in dead_clients:
            self._clients.discard(ws)

    async def _broadcast_error(self, message: str) -> None:
        """Forward an error message to all attached WebSocket clients."""
        dead_clients = []
        for ws in list(self._clients):
            try:
                if not ws.closed:
                    await ws.send_json({"type": "error", "message": message})
            except Exception:
                dead_clients.append(ws)
        for ws in dead_clients:
            self._clients.discard(ws)

    async def _broadcast_exit(self, code: int) -> None:
        """Forward an exit event to all attached WebSocket clients."""
        self.alive = False

        # Update persist store
        if self._store:
            self._store.save(
                session_id=self.session_id,
                status="exited",
                kind=self.kind,
            )

        dead_clients = []
        for ws in list(self._clients):
            try:
                if not ws.closed:
                    await ws.send_json({"type": "exit", "code": code})
            except Exception:
                dead_clients.append(ws)
        for ws in dead_clients:
            self._clients.discard(ws)

    async def _broadcast_metadata(self, metadata: Dict[str, Any]) -> None:
        """Forward metadata events to all attached WebSocket clients."""
        dead_clients = []
        for ws in list(self._clients):
            try:
                if not ws.closed:
                    await ws.send_json({"type": "metadata", **metadata})
            except Exception:
                dead_clients.append(ws)
        for ws in dead_clients:
            self._clients.discard(ws)

    # ------------------------------------------------------------------
    # New operations (same as T3 Code)
    # ------------------------------------------------------------------

    async def clear(self) -> None:
        """Clear terminal history and notify all clients."""
        if self._terminal:
            await self._terminal.clear_history()

        # Notify all clients
        dead_clients = []
        for ws in list(self._clients):
            try:
                if not ws.closed:
                    await ws.send_json({"type": "history_cleared"})
            except Exception:
                dead_clients.append(ws)
        for ws in dead_clients:
            self._clients.discard(ws)

    async def restart(self, cols: int = 80, rows: int = 24) -> bool:
        """Restart the terminal session (keep same tab).

        Kills the current process and starts a new one.
        Returns True if restart was successful.
        """
        if self._terminal:
            # Kill existing terminal
            await self._terminal.kill()

            # Start new terminal
            if self.kind == "ssh":
                # For SSH, we need the original connection params
                # For now, just return False as SSH restart requires storing params
                return False
            else:
                self._terminal = LocalTerminal(self.session_id)
                ok = await self._terminal.start(cols, rows)

                if ok:
                    # Re-attach all clients
                    for ws in list(self._clients):
                        callback = TerminalCallback(
                            on_output=self._broadcast_output,
                            on_error=self._broadcast_error,
                            on_exit=self._broadcast_exit,
                            on_metadata=self._broadcast_metadata,
                        )
                        self._terminal.attach(callback)

                    # Send snapshot to all clients
                    snapshot = self._terminal.history
                    dead_clients = []
                    for ws in list(self._clients):
                        try:
                            if not ws.closed:
                                await ws.send_json({
                                    "type": "snapshot",
                                    "history": snapshot,
                                })
                        except Exception:
                            dead_clients.append(ws)
                    for ws in dead_clients:
                        self._clients.discard(ws)

                    return True
        return False

    # ------------------------------------------------------------------
    # Client -> session delegation
    # ------------------------------------------------------------------

    async def write(self, data: str) -> None:
        """Write client input to the underlying terminal session."""
        if self._terminal:
            await self._terminal.write(data)

    async def resize(self, cols: int, rows: int) -> None:
        """Resize the underlying terminal session."""
        if self._terminal:
            await self._terminal.resize(cols, rows)

    async def kill(self) -> None:
        """Explicitly close the terminal session (user clicked X).

        Kills the process and removes the session from the registry.
        """
        self.alive = False

        if self._terminal:
            await self._terminal.kill()
            self._terminal = None

        # Update persist store
        if self._store:
            self._store.save(
                session_id=self.session_id,
                status="destroyed",
                kind=self.kind,
            )

        # Notify all remaining clients
        for ws in list(self._clients):
            try:
                if not ws.closed:
                    await ws.send_json({
                        "type": "session_closed",
                        "session_id": self.session_id,
                    })
            except (ConnectionError, RuntimeError):
                logger.debug("Failed to notify client of session close", exc_info=True)
            except Exception:
                logger.warning("Unexpected error notifying client of session close", exc_info=True)
        self._clients.clear()

        _sessions.pop(self.session_id, None)

    async def close(self) -> None:
        """Close the session.  Alias for kill for backward compat."""
        await self.kill()


# Active terminal sessions: session_id -> _TerminalSession
_sessions: Dict[str, _TerminalSession] = {}


def get_session(session_id: str) -> Optional[_TerminalSession]:
    """Look up an active session by ID."""
    return _sessions.get(session_id)


def list_sessions() -> List[_TerminalSession]:
    """List all active sessions."""
    return list(_sessions.values())


async def recover_sessions(store: TerminalSessionStore) -> None:
    """Recover surviving terminal sessions from the persistence store.

    Called during server startup.  Scans the persist directory for
    saved sessions and attempts to reattach to any that are still alive.

    Note: PTY handles (ConPTY on Windows, pty fd on Unix) are lost across
    server restarts.  Recovered sessions are marked as non-reattachable
    and can only display persisted offline output in read-only mode.
    """
    persist_dir = store.persist_dir
    if not persist_dir.exists():
        return

    def callback_factory(session_id: str) -> TerminalCallback:
        session = _sessions.get(session_id)
        if session:
            return TerminalCallback(
                on_output=session._broadcast_output,
                on_error=session._broadcast_error,
                on_exit=session._broadcast_exit,
            )
        return TerminalCallback()

    recovered = await LocalTerminal.recover_sessions(persist_dir, callback_factory)

    import time
    now = time.time()

    for session_id, terminal in recovered.items():
        session = _TerminalSession(session_id, "local")
        session._terminal = terminal
        session._store = store

        # Load metadata from store for additional info
        meta = store.load(session_id) if store else None
        if meta:
            session.name = meta.get("name")
            created_at = meta.get("created_at", 0)
            # If session is older than 24 hours, PID reuse is likely — treat as dead
            if terminal.alive and (now - created_at) > 86400:
                terminal.alive = False
                logger.warning(
                    "Session %s too old (age=%.0fs), treating as dead to avoid PID reuse",
                    session_id, now - created_at,
                )

        session.alive = terminal.alive

        # All recovered sessions are non-reattachable (PTY handles lost)
        session.reattachable = False
        _sessions[session_id] = session

        if terminal.alive:
            logger.info("Recovered alive session (read-only): %s", session_id)
        else:
            logger.info("Recovered dead session: %s", session_id)


async def terminal_ws(request: aiohttp.web.Request) -> aiohttp.web.WebSocketResponse:
    """WebSocket endpoint at /v1/webui/ws/terminal/{session_id}.

    Protocol (client -> server):
      {"type": "init", "kind": "local"|"ssh", "cols": N, "rows": N, ...ssh_params}
      {"type": "input", "data": "..."}
      {"type": "resize", "cols": N, "rows": N}
      {"type": "close_session"}
      {"type": "ping"}

    Protocol (server -> client):
      {"type": "ready", "session_id": "..."}
      {"type": "mode", "mode": "conpty"|"pipe"}
      {"type": "output", "data": "..."}
      {"type": "error", "message": "..."}
      {"type": "exit", "code": N}
      {"type": "session_closed", "session_id": "..."}
      {"type": "existing_sessions", "sessions": [...]}
    """
    session_id = request.match_info.get("session_id", str(uuid.uuid4()))

    ws = aiohttp.web.WebSocketResponse(heartbeat=30.0)
    await ws.prepare(request)

    store = get_terminal_store()
    session: Optional[_TerminalSession] = None
    initialized = False

    try:
        # Send existing sessions list on connect (for frontend recovery)
        existing = []
        for sid, s in _sessions.items():
            existing.append({
                "session_id": sid,
                "kind": s.kind,
                "alive": s.alive,
                "name": s.name,
            })
        if existing:
            try:
                await ws.send_json({
                    "type": "existing_sessions",
                    "sessions": existing,
                })
            except (ConnectionError, RuntimeError):
                logger.debug("Failed to send existing sessions list", exc_info=True)
            except Exception:
                logger.warning("Unexpected error sending existing sessions list", exc_info=True)

        async for msg in ws:
            if msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                break

            if msg.type != aiohttp.WSMsgType.TEXT:
                continue

            try:
                payload = json.loads(msg.data)
            except (json.JSONDecodeError, TypeError):
                continue

            msg_type = payload.get("type")

            if msg_type == "init":
                # Initialize or reattach to terminal session
                kind = payload.get("kind", "local")
                cols = int(payload.get("cols", 80))
                rows = int(payload.get("rows", 24))
                tab_name = payload.get("name")

                # Check if session already exists (reattach)
                existing_session = _sessions.get(session_id)
                if existing_session and existing_session.alive and not existing_session.reattachable:
                    # Non-reattachable session: serve offline output only
                    session = existing_session
                    session.attach_client(ws)
                    await ws.send_json({"type": "ready", "session_id": session_id})
                    await ws.send_json({"type": "mode", "mode": "pipe"})
                    # Deliver offline history
                    if session._store:
                        offline = session._store.consume_offline_output(session_id)
                        if offline:
                            await ws.send_json({"type": "output", "data": offline})
                    # Signal that the process is no longer interactive
                    await ws.send_json({"type": "exit", "code": -1})
                    initialized = True

                elif existing_session and existing_session.alive:
                    # Reattach to existing session
                    session = existing_session
                    buffered = session.attach_client(ws)

                    # Send ready message
                    await ws.send_json({"type": "ready", "session_id": session_id})

                    # Send mode
                    if session.kind == "ssh":
                        mode = "conpty"
                    else:
                        terminal = session._terminal
                        mode = (
                            "conpty"
                            if terminal and getattr(terminal, "_conpty", None) is not None
                            else "pipe"
                        )
                    await ws.send_json({"type": "mode", "mode": mode})

                    # Flush buffered offline output
                    if buffered:
                        await ws.send_json({"type": "output", "data": buffered})

                    # Send resize to match new client's dimensions
                    await session.resize(cols, rows)
                    initialized = True

                else:
                    # Create new session
                    if existing_session:
                        # Clean up dead session
                        _sessions.pop(session_id, None)

                    session = _TerminalSession(session_id, kind)
                    session._store = store
                    session.name = tab_name
                    _sessions[session_id] = session

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

                    if ok:
                        session.attach_client(ws)
                        await ws.send_json({"type": "ready", "session_id": session_id})
                        # Signal terminal mode so frontend can toggle local echo.
                        if kind == "ssh":
                            mode = "conpty"
                        else:
                            terminal = session._terminal
                            mode = (
                                "conpty"
                                if terminal and getattr(terminal, "_conpty", None) is not None
                                else "pipe"
                            )
                        await ws.send_json({"type": "mode", "mode": mode})
                        initialized = True
                    else:
                        # No callback was attached yet (attach_client runs only
                        # on success), so _broadcast_error was never called.
                        # Send an explicit error directly to the WebSocket.
                        if kind == "ssh":
                            await ws.send_json({
                                "type": "error",
                                "message": "Failed to start SSH terminal. Check connection settings and that the remote host is reachable.",
                            })
                        else:
                            await ws.send_json({
                                "type": "error",
                                "message": "Failed to start local terminal. Check that a shell is available and PTY is supported.",
                            })
                        _sessions.pop(session_id, None)

            elif msg_type == "input" and session:
                data = payload.get("data", "")
                if data:
                    await session.write(data)

            elif msg_type == "resize" and session:
                cols = int(payload.get("cols", 80))
                rows = int(payload.get("rows", 24))
                await session.resize(cols, rows)

            elif msg_type == "close_session":
                # User explicitly closed the tab -- kill the process
                if session:
                    await session.kill()
                    session = None
                    initialized = False

            elif msg_type == "clear" and session:
                # Clear terminal history
                await session.clear()

            elif msg_type == "restart" and session:
                # Restart terminal session
                cols = int(payload.get("cols", 80))
                rows = int(payload.get("rows", 24))
                ok = await session.restart(cols, rows)
                if not ok:
                    await ws.send_json({
                        "type": "error",
                        "message": "Failed to restart terminal",
                    })

            elif msg_type == "ping":
                await ws.send_json({"type": "pong"})

    finally:
        # WS disconnected -- detach this client (do NOT kill the process)
        if session and initialized:
            session.detach_client(ws)
            logger.debug(
                "WS disconnected from session %s (%d clients remaining)",
                session_id,
                len(session._clients),
            )

    return ws


async def terminal_sessions_api(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/webui/terminal/sessions -- list active terminal sessions."""
    store = get_terminal_store()
    result = []

    # Active in-memory sessions
    for sid, session in _sessions.items():
        result.append({
            "session_id": sid,
            "kind": session.kind,
            "alive": session.alive,
            "clients": len(session._clients),
            "name": session.name,
        })

    # Also include persisted sessions that aren't in memory
    persisted = store.list_all()
    active_ids = set(_sessions.keys())
    for meta in persisted:
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
