"""Tests for src/webui/routers/terminal.py.

Covers the terminal WebSocket handler error paths (local and SSH startup
failures send explicit error messages to the client) and the
_TerminalSession wrapper's start methods.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from src.webui.routers import terminal as terminal_module
from src.webui.routers.terminal import _TerminalSession, terminal_ws


class _FakeWS:
    """Lightweight WebSocket stand-in for handler tests.

    Records all ``send_json`` payloads and yields pre-configured
    messages via ``async for``.
    """

    def __init__(self, messages: List[Dict[str, Any]]) -> None:
        self._messages = messages
        self.sent: List[Dict[str, Any]] = []
        self.closed = False

    async def prepare(self, request: Any) -> "_FakeWS":
        return self

    async def send_json(self, data: Dict[str, Any]) -> None:
        self.sent.append(data)

    def __aiter__(self):
        async def _gen():
            for msg in self._messages:
                yield msg
        return _gen()


def _ws_msg(msg_type: Any, data: Any = None) -> MagicMock:
    """Build a mock ``aiohttp.WSMsgType`` message."""
    m = MagicMock()
    m.type = msg_type
    m.data = data
    return m


# ------------------------------------------------------------------
# terminal_ws handler -- error paths
# ------------------------------------------------------------------


class TestTerminalWSErrorPath:
    """Verify that the WebSocket handler sends an explicit error JSON
    message to the client when terminal startup fails.

    Before the bug fix, ``_broadcast_error`` was never attached in the
    failure path (``attach_client`` only runs on success), so the
    client received nothing -- a silent failure.
    """

    @pytest.mark.asyncio
    async def test_local_start_failure_sends_error(self):
        ws = _FakeWS(messages=[
            _ws_msg(aiohttp.WSMsgType.TEXT, json.dumps({
                "type": "init", "kind": "local", "cols": 80, "rows": 24,
            })),
            _ws_msg(aiohttp.WSMsgType.CLOSE),
        ])
        request = MagicMock()
        request.match_info = {"session_id": "test-local-err"}

        with patch(
            "aiohttp.web.WebSocketResponse",
            return_value=ws,
        ), patch(
            "src.webui.routers.terminal.get_terminal_store",
            return_value=MagicMock(),
        ), patch(
            "src.webui.routers.terminal.LocalTerminal",
        ) as MockLT, patch.object(
            terminal_module, "_sessions", {},
        ):
            mock_terminal = MagicMock()
            mock_terminal.start = AsyncMock(return_value=False)
            MockLT.return_value = mock_terminal

            await terminal_ws(request)

        errors = [m for m in ws.sent if m.get("type") == "error"]
        assert len(errors) == 1
        assert "Failed to start local terminal" in errors[0]["message"]
        assert all(m.get("type") != "ready" for m in ws.sent)

    @pytest.mark.asyncio
    async def test_ssh_start_failure_sends_error(self):
        ws = _FakeWS(messages=[
            _ws_msg(aiohttp.WSMsgType.TEXT, json.dumps({
                "type": "init", "kind": "ssh",
                "host": "192.0.2.1", "port": 22,
                "username": "testuser", "password": "testpass",
                "cols": 80, "rows": 24,
            })),
            _ws_msg(aiohttp.WSMsgType.CLOSE),
        ])
        request = MagicMock()
        request.match_info = {"session_id": "test-ssh-err"}

        with patch(
            "aiohttp.web.WebSocketResponse",
            return_value=ws,
        ), patch(
            "src.webui.routers.terminal.get_terminal_store",
            return_value=MagicMock(),
        ), patch(
            "src.webui.routers.terminal.SSHTerminal",
        ) as MockST, patch.object(
            terminal_module, "_sessions", {},
        ):
            mock_terminal = MagicMock()
            mock_terminal.start = AsyncMock(return_value=False)
            MockST.return_value = mock_terminal

            await terminal_ws(request)

        errors = [m for m in ws.sent if m.get("type") == "error"]
        assert len(errors) == 1
        assert "Failed to start SSH terminal" in errors[0]["message"]
        assert all(m.get("type") != "ready" for m in ws.sent)

    @pytest.mark.asyncio
    async def test_failed_session_cleaned_from_registry(self):
        """After a failed start, the session must be removed from _sessions."""
        ws = _FakeWS(messages=[
            _ws_msg(aiohttp.WSMsgType.TEXT, json.dumps({
                "type": "init", "kind": "local", "cols": 80, "rows": 24,
            })),
            _ws_msg(aiohttp.WSMsgType.CLOSE),
        ])
        request = MagicMock()
        request.match_info = {"session_id": "test-cleanup"}

        sessions: Dict[str, Any] = {}

        with patch(
            "aiohttp.web.WebSocketResponse",
            return_value=ws,
        ), patch(
            "src.webui.routers.terminal.get_terminal_store",
            return_value=MagicMock(),
        ), patch(
            "src.webui.routers.terminal.LocalTerminal",
        ) as MockLT, patch.object(
            terminal_module, "_sessions", sessions,
        ):
            mock_terminal = MagicMock()
            mock_terminal.start = AsyncMock(return_value=False)
            MockLT.return_value = mock_terminal

            await terminal_ws(request)

        assert "test-cleanup" not in sessions

    @pytest.mark.asyncio
    async def test_existing_sessions_sent_before_error(self):
        """The existing_sessions list is delivered even if init fails."""
        ws = _FakeWS(messages=[
            _ws_msg(aiohttp.WSMsgType.TEXT, json.dumps({
                "type": "init", "kind": "ssh", "host": "192.0.2.1",
            })),
            _ws_msg(aiohttp.WSMsgType.CLOSE),
        ])
        request = MagicMock()
        request.match_info = {"session_id": "test-existing"}

        existing_sess = MagicMock()
        existing_sess.kind = "local"
        existing_sess.alive = True
        existing_sess.name = "tab1"

        with patch(
            "aiohttp.web.WebSocketResponse",
            return_value=ws,
        ), patch(
            "src.webui.routers.terminal.get_terminal_store",
            return_value=MagicMock(),
        ), patch(
            "src.webui.routers.terminal.SSHTerminal",
        ) as MockST, patch.object(
            terminal_module, "_sessions", {"other-id": existing_sess},
        ):
            mock_terminal = MagicMock()
            mock_terminal.start = AsyncMock(return_value=False)
            MockST.return_value = mock_terminal

            await terminal_ws(request)

        types = [m.get("type") for m in ws.sent]
        assert "existing_sessions" in types
        assert "error" in types
        assert types.index("existing_sessions") < types.index("error")


# ------------------------------------------------------------------
# _TerminalSession unit tests
# ------------------------------------------------------------------


class TestTerminalSession:
    """Unit tests for the _TerminalSession wrapper."""

    @pytest.mark.asyncio
    async def test_start_local_failure(self):
        session = _TerminalSession("s1", "local")
        session._store = MagicMock()

        with patch(
            "src.webui.routers.terminal.LocalTerminal",
        ) as MockLT:
            mock_terminal = MagicMock()
            mock_terminal.start = AsyncMock(return_value=False)
            MockLT.return_value = mock_terminal

            result = await session.start_local(cols=120, rows=40)

        assert result is False
        assert session.alive is False
        session._store.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_local_success(self):
        session = _TerminalSession("s2", "local")
        session._store = MagicMock()

        with patch(
            "src.webui.routers.terminal.LocalTerminal",
        ) as MockLT:
            mock_terminal = MagicMock()
            mock_terminal.start = AsyncMock(return_value=True)
            mock_terminal.pid = 42
            MockLT.return_value = mock_terminal

            result = await session.start_local(cols=80, rows=24)

        assert result is True
        assert session.alive is True
        session._store.save.assert_called_once_with(
            session_id="s2", pid=42, cols=80, rows=24,
            kind="local", name=None, status="alive",
        )

    @pytest.mark.asyncio
    async def test_start_ssh_failure(self):
        session = _TerminalSession("s3", "ssh")
        session._store = MagicMock()

        with patch(
            "src.webui.routers.terminal.SSHTerminal",
        ) as MockST:
            mock_terminal = MagicMock()
            mock_terminal.start = AsyncMock(return_value=False)
            MockST.return_value = mock_terminal

            result = await session.start_ssh(
                host="192.0.2.1", port=22,
                username="user", password="pass",
            )

        assert result is False
        assert session.alive is False
        session._store.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_ssh_success(self):
        session = _TerminalSession("s4", "ssh")
        session._store = MagicMock()

        with patch(
            "src.webui.routers.terminal.SSHTerminal",
        ) as MockST:
            mock_terminal = MagicMock()
            mock_terminal.start = AsyncMock(return_value=True)
            MockST.return_value = mock_terminal

            result = await session.start_ssh(
                host="192.0.2.1", port=22,
                username="user", password="pass",
                cols=100, rows=30,
            )

        assert result is True
        assert session.alive is True
        session._store.save.assert_called_once_with(
            session_id="s4", pid=None, cols=100, rows=30,
            kind="ssh",
            ssh_config={"host": "192.0.2.1", "port": 22, "username": "user"},
            name=None, status="alive",
        )

    @pytest.mark.asyncio
    async def test_clear_history(self):
        """Test clear_history sends history_cleared to all clients."""
        session = _TerminalSession("s5", "local")
        session._terminal = MagicMock()
        session._terminal.clear_history = AsyncMock()
        client = MagicMock()
        client.closed = False
        session._clients = {client}

        await session.clear()

        session._terminal.clear_history.assert_called_once()
        client.send_json.assert_called_once_with({"type": "history_cleared"})

    @pytest.mark.asyncio
    async def test_restart_terminal(self):
        """Test restart kills old terminal and starts new one."""
        session = _TerminalSession("s6", "local")
        old_terminal = MagicMock()
        old_terminal.kill = AsyncMock()
        session._terminal = old_terminal
        session._clients = set()

        with patch(
            "src.webui.routers.terminal.LocalTerminal",
        ) as MockLT:
            mock_terminal = MagicMock()
            mock_terminal.start = AsyncMock(return_value=True)
            mock_terminal.history = "test history"
            MockLT.return_value = mock_terminal

            result = await session.restart(cols=80, rows=24)

        assert result is True
        old_terminal.kill.assert_called_once()
        MockLT.assert_called_once_with("s6")
        mock_terminal.start.assert_called_once_with(80, 24)

    @pytest.mark.asyncio
    async def test_metadata_broadcast(self):
        """Test metadata is broadcast to all clients."""
        session = _TerminalSession("s7", "local")
        client1 = MagicMock()
        client1.closed = False
        client2 = MagicMock()
        client2.closed = False
        session._clients = {client1, client2}

        metadata = {"has_running_subprocess": True, "child_command_label": "python"}
        await session._broadcast_metadata(metadata)

        for client in [client1, client2]:
            client.send_json.assert_called_once_with({
                "type": "metadata",
                "has_running_subprocess": True,
                "child_command_label": "python",
            })
