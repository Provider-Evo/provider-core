from __future__ import annotations

"""L3 热重载前关闭长连接，避免 runner.cleanup() 无限等待。"""

import asyncio
from typing import Iterable

import aiohttp.web

from echotools.logger.manager import get_logger

__all__ = ["close_live_connections"]

logger = get_logger(__name__)

_CLOSE_TIMEOUT_S = 1.0


async def _close_sockets(sockets: Iterable[aiohttp.web.WebSocketResponse]) -> int:
    closed = 0
    for ws in list(sockets):
        try:
            await asyncio.wait_for(ws.close(), timeout=_CLOSE_TIMEOUT_S)
            closed += 1
        except Exception:
            try:
                ws.close()
            except Exception:
                pass
    return closed


async def close_live_connections() -> None:
    """关闭 WebUI 日志、终端、请求监控等 WebSocket，释放 aiohttp shutdown 等待。"""
    total = 0

    try:
        from src.webui.core.logs_ws import log_broker

        async with log_broker._lock:
            sockets = list(log_broker._sockets)
            log_broker._sockets.clear()
        total += await _close_sockets(sockets)
    except Exception as exc:
        logger.debug("关闭日志 WebSocket 失败: %s", exc)

    try:
        from src.webui.routers.session.terminal import list_sessions

        terminal_sockets: list[aiohttp.web.WebSocketResponse] = []
        for session in list_sessions():
            terminal_sockets.extend(list(session._clients))
        total += await _close_sockets(terminal_sockets)
    except Exception as exc:
        logger.debug("关闭终端 WebSocket 失败: %s", exc)

    try:
        from src.webui.services.request_log import request_broker

        broker_sockets = getattr(request_broker, "_sockets", None)
        if broker_sockets is not None:
            sockets = list(broker_sockets)
            broker_sockets.clear()
            total += await _close_sockets(sockets)
    except Exception as exc:
        logger.debug("关闭请求监控 WebSocket 失败: %s", exc)

    if total:
        logger.info("L3 热重载前已关闭 %d 个 WebSocket 连接", total)
