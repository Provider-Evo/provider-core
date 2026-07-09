from __future__ import annotations

"""重启前运行时清理。"""

import asyncio
from typing import Any, Optional

from src.core.utils.observability import get_observability_services
from src.foundation.logger import get_logger

__all__ = ["prepare_graceful_restart", "stop_runtime_before_restart"]

logger = get_logger(__name__)

_RUNTIME_STOP_TIMEOUT_S = 3.0


def _save_pre_restart_stats() -> None:
    obs = get_observability_services()
    try:
        obs.save_stats()
    except Exception as exc:
        logger.debug("重启前保存统计失败: %s", exc)
    try:
        obs.save_requests()
    except Exception as exc:
        logger.debug("重启前保存请求日志失败: %s", exc)


async def _broadcast_restart_notice() -> None:
    obs = get_observability_services()
    try:
        await obs.broadcast_log({"type": "system_restarting", "message": "服务正在重启"})
    except Exception as exc:
        logger.debug("重启前广播 WS 失败: %s", exc)


async def _save_terminal_states() -> None:
    obs = get_observability_services()
    try:
        obs.save_terminal_states()
    except Exception as exc:
        logger.debug("重启前保存终端状态失败: %s", exc)


async def prepare_graceful_restart(
    registry: Optional[Any] = None,
    session: Optional[Any] = None,
    *,
    reason: str = "",
) -> None:
    """在触发退出码 42 前持久化状态并通知前端。"""
    del registry, session
    logger.info("重启前清理%s", f": {reason}" if reason else "")
    _save_pre_restart_stats()
    await _broadcast_restart_notice()
    await _save_terminal_states()


async def stop_runtime_before_restart(
    registry: Optional[Any] = None,
    session: Optional[Any] = None,
) -> None:
    """快速重启前停止插件运行时（对齐 MaiBot，不等待完整 HTTP 关停链）。"""
    del session
    runtime = None
    if registry is not None:
        runtime = getattr(registry, "_external_loader", None)
    if runtime is None:
        try:
            from src.core.server.plugins.runtime import get_plugin_runtime

            runtime = get_plugin_runtime()
        except Exception as exc:
            logger.debug("获取插件运行时失败: %s", exc)
    if runtime is None:
        return
    try:
        await asyncio.wait_for(runtime.close(), timeout=_RUNTIME_STOP_TIMEOUT_S)
    except asyncio.TimeoutError:
        logger.warning("插件运行时关闭超时 (%ss)，继续快速重启", _RUNTIME_STOP_TIMEOUT_S)
    except Exception as exc:
        logger.warning("插件运行时关闭失败: %s", exc)
