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

# 模块颜色映射（hex 前景色）
MODULE_COLORS: Dict[str, str] = {
    "server": "#8b949e",
    "watcher": "#d29922",
    "webui": "#79c0ff",
    "webui.routers": "#79c0ff",
    "webui.routers.websocket": "#a5d6ff",
    "webui.logs_ws": "#a5d6ff",
    "webui.services": "#79c0ff",
    "webui.services.request_log": "#a5d6ff",
    "dispatch": "#3fb950",
    "dispatch.runtime": "#56d364",
    "middleware": "#da77f2",
    "middleware.request_broker": "#d2a8ff",
    "core.terminal_sessions": "#f0883e",
    "core.server": "#8b949e",
    "core.config": "#79c0ff",
    "core.dispatch": "#3fb950",
    "config.main_config": "#79c0ff",
}

# 日志 ID 生成器
_log_counter = 0


def _make_log_id() -> str:
    global _log_counter
    _log_counter += 1
    return f"{int(time.time() * 1000)}_{_log_counter}"


def _resolve_module_color(module_name: str) -> str:
    """按前缀匹配模块颜色。"""
    if not module_name:
        return ""
    # 精确匹配
    if module_name in MODULE_COLORS:
        return MODULE_COLORS[module_name]
    # 逐级前缀匹配
    parts = module_name.split(".")
    for i in range(len(parts), 0, -1):
        candidate = ".".join(parts[:i])
        if candidate in MODULE_COLORS:
            return MODULE_COLORS[candidate]
    return ""


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
            level_name = record["level"].name
            msg_text = str(record["message"])
            module_name = record["extra"].get("module_name", "")
            payload = {
                "type": "log",
                "id": _make_log_id(),
                "timestamp": record["time"].strftime("%Y-%m-%dT%H:%M:%S"),
                "level": level_name,  # 完整级别名 "INFO" 而非 "I"
                "module": module_name,
                "message": msg_text,
                "moduleColor": _resolve_module_color(module_name),
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
