from __future__ import annotations

"""进程级重启信号 — 优雅关闭后由 Worker 以退出码 42 通知 Runner。"""

import asyncio
import os
from typing import Optional

from src.foundation.logger import get_logger

__all__ = [
    "bind_worker_shutdown",
    "consume_restart_flag",
    "request_graceful_restart",
]

logger = get_logger(__name__)

_STOP_EVENT: Optional[asyncio.Event] = None
_RESTART_AFTER_SHUTDOWN = False


def bind_worker_shutdown(stop_event: asyncio.Event) -> None:
    """绑定 Worker 主循环的停止事件。"""
    global _STOP_EVENT
    _STOP_EVENT = stop_event


def consume_restart_flag() -> bool:
    """读取并清除「关闭后应以退出码 42 重启」标记。"""
    global _RESTART_AFTER_SHUTDOWN
    flag = _RESTART_AFTER_SHUTDOWN
    _RESTART_AFTER_SHUTDOWN = False
    return flag


async def request_graceful_restart(*, reason: str = "") -> None:
    """请求优雅重启：触发 stop_event，由 ``main`` 在 shutdown 后以退出码 42 退出。"""
    global _RESTART_AFTER_SHUTDOWN
    _RESTART_AFTER_SHUTDOWN = True
    if reason:
        logger.info("请求进程重启: %s", reason)
    else:
        logger.info("请求进程重启")
    if _STOP_EVENT is not None:
        _STOP_EVENT.set()
    else:
        os._exit(42)
