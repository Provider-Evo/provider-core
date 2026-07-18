from __future__ import annotations

"""TerminalSession 主类 — 组合 lifecycle/clients/broadcast mixin。"""

import asyncio
from typing import Any, Dict, Optional, Set, Tuple

import aiohttp.web
from echotools.terminal import TerminalCallback

from src.core.server.terminal.sess import TerminalSessionStore
from src.foundation.logger import get_logger
from src.webui.routers.session.terminal.out_bridge import (
    BridgedLocalTerminal,
    BridgedSSHTerminal,
    BridgedTmuxTerminal,
)
from src.webui.routers.session.terminal.session_all.bcast import _BroadcastMixin
from src.webui.routers.session.terminal.session_all.clients import _ClientsMixin
from src.webui.routers.session.terminal.session_all.lifecyc import _LifecycleMixin

logger = get_logger(__name__)


class TerminalSession(_LifecycleMixin, _ClientsMixin, _BroadcastMixin):
    """服务端终端会话：管理底层进程与已连接的 WebSocket 客户端。"""

    _logger = logger

    def __init__(self, session_id: str, kind: str) -> None:
        self.session_id = session_id
        self.kind = kind
        self._terminal: Optional[
            BridgedLocalTerminal | BridgedSSHTerminal | BridgedTmuxTerminal
        ] = None
        self._clients: Set[aiohttp.web.WebSocketResponse] = set()
        self._client_callbacks: Dict[aiohttp.web.WebSocketResponse, TerminalCallback] = {}
        self._client_writable: Dict[aiohttp.web.WebSocketResponse, bool] = {}
        self._primary_client: Optional[aiohttp.web.WebSocketResponse] = None
        self._store: Optional[TerminalSessionStore] = None
        self.alive: bool = False
        self.name: Optional[str] = None
        self.reattachable: bool = True
        self.readonly: bool = False
        self._ssh_config: Optional[Dict[str, Any]] = None
        self._connection_id: Optional[str] = None
        self.last_start_error: Optional[str] = None
        self._output_queue: "asyncio.Queue[Tuple[int, bytes]]" = asyncio.Queue()
        self._writer_task: Optional[asyncio.Task[None]] = None
        self._paused_clients: Set[aiohttp.web.WebSocketResponse] = set()
