"""connection_drain 模块 — 项目标准模块。

职责：
    作为 Provider-Evo 项目标准模块，提供 connection_drain 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""

import asyncio
from typing import Iterable

import aiohttp.web

from src.core.utils.compat.observability import get_observability_services
from src.foundation.logger import get_logger

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
    obs = get_observability_services()
    total = 0

    for closer_name, closer in (
        ("日志", obs.close_log_sockets),
        ("终端", obs.close_terminal_sockets),
        ("请求监控", obs.close_request_monitor_sockets),
    ):
        try:
            sockets = await closer()
            total += await _close_sockets(sockets)
        except Exception as exc:
            logger.debug("关闭%s WebSocket 失败: %s", closer_name, exc)

    if total:
        logger.info("L3 热重载前已关闭 %d 个 WebSocket 连接", total)
