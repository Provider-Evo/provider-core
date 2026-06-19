from __future__ import annotations

"""WebUI Terminal WebSocket router.

Provides local and SSH remote terminal sessions via WebSocket,
using xterm.js on the frontend.

Terminal process management is delegated to ``echotools.terminal``
(``LocalTerminal`` / ``SSHTerminal``).  This module only handles the
WebSocket transport layer via ``_TerminalBridge``.
"""

import json
import logging
import uuid
from typing import Any, Dict, Optional

import aiohttp.web
from echotools.terminal import LocalTerminal, SSHTerminal, TerminalCallback

logger = logging.getLogger(__name__)

__all__ = ["terminal_ws", "terminal_sessions_api"]

# Active terminal sessions: session_id -> _TerminalBridge
_sessions: Dict[str, "_TerminalBridge"] = {}


class _TerminalBridge:
    """Bridges echotools TerminalSession to aiohttp WebSocket.

    Holds a reference to the WebSocket response and wires the
    ``TerminalCallback`` hooks so that output / error / exit events
    produced by the echotools session are forwarded to the client as
    JSON messages.
    """

    def __init__(self, session_id: str, kind: str, ws: aiohttp.web.WebSocketResponse) -> None:
        self.session_id = session_id
        self.kind = kind
        self.ws = ws
        self._session: Optional[LocalTerminal | SSHTerminal] = None
        self.alive: bool = False

    # ------------------------------------------------------------------
    # Start helpers
    # ------------------------------------------------------------------

    async def start_local(self, cols: int = 80, rows: int = 24) -> bool:
        """Create and start a ``LocalTerminal`` session."""
        callback = TerminalCallback(
            on_output=self._send_output,
            on_error=self._send_error,
            on_exit=self._send_exit,
        )
        self._session = LocalTerminal(self.session_id, callback)
        ok = await self._session.start(cols, rows)
        if ok:
            self.alive = True
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
        """Create and start an ``SSHTerminal`` session."""
        callback = TerminalCallback(
            on_output=self._send_output,
            on_error=self._send_error,
            on_exit=self._send_exit,
        )
        self._session = SSHTerminal(
            self.session_id,
            host=host,
            port=port,
            username=username,
            password=password or None,
            key_data=key_data or None,
            callback=callback,
        )
        ok = await self._session.start(cols, rows)
        if ok:
            self.alive = True
        return ok

    # ------------------------------------------------------------------
    # Callback implementations (echotools -> WebSocket)
    # ------------------------------------------------------------------

    async def _send_output(self, data: str) -> None:
        """Forward terminal output to the WebSocket client."""
        if self.ws and not self.ws.closed:
            await self.ws.send_json({"type": "output", "data": data})

    async def _send_error(self, message: str) -> None:
        """Forward an error message to the WebSocket client."""
        if self.ws and not self.ws.closed:
            await self.ws.send_json({"type": "error", "message": message})

    async def _send_exit(self, code: int) -> None:
        """Forward an exit event to the WebSocket client."""
        self.alive = False
        if self.ws and not self.ws.closed:
            await self.ws.send_json({"type": "exit", "code": code})

    # ------------------------------------------------------------------
    # Client -> session delegation
    # ------------------------------------------------------------------

    async def write(self, data: str) -> None:
        """Write client input to the underlying terminal session."""
        if self._session:
            await self._session.write(data)

    async def resize(self, cols: int, rows: int) -> None:
        """Resize the underlying terminal session."""
        if self._session:
            await self._session.resize(cols, rows)

    async def close(self) -> None:
        """Close the terminal session and remove it from the registry."""
        self.alive = False
        if self._session:
            await self._session.close()
            self._session = None
        _sessions.pop(self.session_id, None)


async def terminal_ws(request: aiohttp.web.Request) -> aiohttp.web.WebSocketResponse:
    """WebSocket endpoint at /v1/webui/ws/terminal/{session_id}.

    Protocol (client -> server):
      {"type": "init", "kind": "local"|"ssh", "cols": N, "rows": N, ...ssh_params}
      {"type": "input", "data": "..."}
      {"type": "resize", "cols": N, "rows": N}

    Protocol (server -> client):
      {"type": "ready", "session_id": "..."}
      {"type": "output", "data": "..."}
      {"type": "error", "message": "..."}
      {"type": "exit", "code": N}
    """
    session_id = request.match_info.get("session_id", str(uuid.uuid4()))

    ws = aiohttp.web.WebSocketResponse(heartbeat=30.0)
    await ws.prepare(request)

    bridge: Optional[_TerminalBridge] = None

    try:
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
                # Initialize terminal session
                kind = payload.get("kind", "local")
                cols = int(payload.get("cols", 80))
                rows = int(payload.get("rows", 24))

                bridge = _TerminalBridge(session_id, kind, ws)
                _sessions[session_id] = bridge

                if kind == "ssh":
                    ok = await bridge.start_ssh(
                        host=payload.get("host", ""),
                        port=int(payload.get("port", 22)),
                        username=payload.get("username", ""),
                        password=payload.get("password", ""),
                        key_data=payload.get("key_data", ""),
                        cols=cols,
                        rows=rows,
                    )
                else:
                    ok = await bridge.start_local(cols, rows)

                if ok:
                    await ws.send_json({"type": "ready", "session_id": session_id})
                else:
                    # Error already sent via callback (_send_error)
                    _sessions.pop(session_id, None)

            elif msg_type == "input" and bridge:
                data = payload.get("data", "")
                if data:
                    await bridge.write(data)

            elif msg_type == "resize" and bridge:
                cols = int(payload.get("cols", 80))
                rows = int(payload.get("rows", 24))
                await bridge.resize(cols, rows)

            elif msg_type == "ping":
                await ws.send_json({"type": "pong"})

    finally:
        if bridge:
            await bridge.close()

    return ws


async def terminal_sessions_api(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/webui/terminal/sessions -- list active terminal sessions."""
    result = []
    for sid, bridge in _sessions.items():
        result.append({
            "session_id": sid,
            "kind": bridge.kind,
            "alive": bridge.alive,
        })
    return aiohttp.web.json_response(result)
