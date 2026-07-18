"""restart 模块 — 项目标准模块。

职责：
    作为 Provider-Evo 项目标准模块，提供 restart 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""



import asyncio
import os
from typing import Any, Optional

from src.foundation.logger import get_logger

__all__ = [
    "bind_worker_shutdown",
    "consume_restart_flag",
    "request_fast_restart",
    "request_graceful_restart",
    "request_process_restart",
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


def _resolve_fast_restart(fast: Optional[bool]) -> bool:
    if fast is not None:
        return fast
    try:
        from src.foundation.config import get_config

        return bool(get_config().server.fast_restart)
    except Exception:
        return True


async def request_fast_restart(
    *,
    reason: str = "",
    registry: Optional[Any] = None,
    session: Optional[Any] = None,
) -> None:
    """快速进程重启：持久化 → 停插件运行时 → ``os._exit(42)``，跳过完整 ``_shutdown`` 链。"""
    from src.core.server.reload.internal.pre_restart import (
        prepare_graceful_restart,
        stop_runtime_before_restart,
    )

    if reason:
        logger.info("请求快速重启: %s", reason)
    else:
        logger.info("请求快速重启")
    await prepare_graceful_restart(registry, session, reason=reason)
    try:
        await stop_runtime_before_restart(registry, session)
    except Exception as exc:
        logger.warning("快速重启前停止运行时失败，继续 exit 42: %s", exc)
    logger.info("快速重启退出 (exit 42)")
    os._exit(42)


async def request_graceful_restart(*, reason: str = "") -> None:
    """完整优雅重启：触发 stop_event，由 Worker ``_shutdown`` 后 exit 42。"""
    global _RESTART_AFTER_SHUTDOWN
    _RESTART_AFTER_SHUTDOWN = True
    if reason:
        logger.info("请求优雅重启: %s", reason)
    else:
        logger.info("请求优雅重启")
    if _STOP_EVENT is not None:
        _STOP_EVENT.set()
    else:
        os._exit(42)


async def request_process_restart(
    *,
    reason: str = "",
    registry: Optional[Any] = None,
    session: Optional[Any] = None,
    fast: Optional[bool] = None,
) -> None:
    """按 ``server.fast_restart`` 或 ``fast`` 参数选择快速/优雅进程重启。"""
    if _resolve_fast_restart(fast):
        await request_fast_restart(
            reason=reason,
            registry=registry,
            session=session,
        )
        return
    from src.core.server.reload.internal.pre_restart import prepare_graceful_restart

    await prepare_graceful_restart(registry, session, reason=reason)
    await request_graceful_restart(reason=reason)
