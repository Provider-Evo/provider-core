from __future__ import annotations

"""WebUI 日志 WebSocket 代理。"""

import asyncio
import json
import time
from collections import deque
from typing import Any, Deque, Dict, Set

import aiohttp.web

__all__ = ["WebUILogBroker", "log_broker"]

# 保留最近 200 条日志
LOG_BUFFER_SIZE = 200


class WebUILogBroker:
    """WebUI 日志事件广播器。"""

    def __init__(self) -> None:
        self._sockets: Set[aiohttp.web.WebSocketResponse] = set()
        self._lock = asyncio.Lock()
        self._buffer: Deque[Dict[str, Any]] = deque(maxlen=LOG_BUFFER_SIZE)

    async def register(self, socket: aiohttp.web.WebSocketResponse) -> None:
        async with self._lock:
            self._sockets.add(socket)

    async def unregister(self, socket: aiohttp.web.WebSocketResponse) -> None:
        async with self._lock:
            self._sockets.discard(socket)

    async def send_history(self, socket: aiohttp.web.WebSocketResponse) -> int:
        """发送历史日志缓冲，返回已发送条数。"""
        async with self._lock:
            history = list(self._buffer)
        count = 0
        for entry in history:
            try:
                await socket.send_json(entry)
                count += 1
            except Exception:
                break
        return count

    async def broadcast(self, payload: Dict[str, Any]) -> None:
        message = json.dumps(payload, ensure_ascii=False)
        # 写入缓冲
        self._buffer.append(payload)
        stale: Set[aiohttp.web.WebSocketResponse] = set()
        async with self._lock:
            for socket in self._sockets:
                try:
                    await socket.send_str(message)
                except Exception:
                    stale.add(socket)
            for socket in stale:
                self._sockets.discard(socket)


log_broker = WebUILogBroker()
