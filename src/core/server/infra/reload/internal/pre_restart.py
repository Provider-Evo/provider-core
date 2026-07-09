from __future__ import annotations

"""重启前运行时清理。"""

from typing import Any, Optional

from src.core.observability import get_observability_services
from src.logger import get_logger

__all__ = ["prepare_graceful_restart"]

logger = get_logger(__name__)


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
    """在触发退出码 42 前持久化状态并关闭长连接。"""
    _ = registry
    _ = session
    logger.info("重启前清理%s", f": {reason}" if reason else "")
    _save_pre_restart_stats()
    await _broadcast_restart_notice()
    await _save_terminal_states()
