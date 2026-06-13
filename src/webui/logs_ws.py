from __future__ import annotations

"""WebUI 日志 WebSocket 代理。"""

import asyncio
import json
import time
from collections import deque
from typing import Any, Deque, Dict, Optional, Set

import aiohttp.web

__all__ = ["WebUILogBroker", "log_broker", "setup_loguru_sink"]

# 保留最近 200 条日志
LOG_BUFFER_SIZE = 200

# 等级缩写映射
_LEVEL_ABBR = {
    "TRACE": "T",
    "DEBUG": "D",
    "INFO": "I",
    "SUCCESS": "S",
    "WARNING": "W",
    "ERROR": "E",
    "CRITICAL": "C",
}


class WebUILogBroker:
    """WebUI 日志事件广播器。"""

    def __init__(self) -> None:
        self._sockets: Set[aiohttp.web.WebSocketResponse] = set()
        self._lock = asyncio.Lock()
        self._buffer: Deque[Dict[str, Any]] = deque(maxlen=LOG_BUFFER_SIZE)
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """保存主事件循环引用。"""
        self._loop = loop

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

    def _loguru_sink(self, message: Any) -> None:
        """loguru sink：同步函数，通过 run_coroutine_threadsafe 推入事件循环。"""
        if message is None or self._loop is None:
            return
        try:
            record = message.record
            payload = {
                "type": "log",
                "timestamp": record["time"].strftime("%H:%M:%S"),
                "level": _LEVEL_ABBR.get(record["level"].name, record["level"].name[0]),
                "module": record["extra"].get("module_name", ""),
                "message": str(record["message"]),
            }
            if self._loop.is_running():
                asyncio.run_coroutine_threadsafe(self.broadcast(payload), self._loop)
        except Exception:
            pass


log_broker = WebUILogBroker()


def setup_loguru_sink() -> None:
    """将 log_broker._loguru_sink 注册为 loguru 的 sink，并保存主事件循环。"""
    try:
        from loguru import logger
        logger.add(log_broker._loguru_sink, level="DEBUG", format="{time:HH:mm:ss} | {level} | {extra[module_name]} | {message}")
        # 保存当前事件循环
        try:
            loop = asyncio.get_running_loop()
            log_broker.set_loop(loop)
        except RuntimeError:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    log_broker.set_loop(loop)
            except Exception:
                pass
    except Exception:
        pass
