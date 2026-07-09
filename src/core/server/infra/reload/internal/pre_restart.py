from __future__ import annotations

"""重启前运行时清理。"""

from typing import Any, Optional

from echotools.logger.manager import get_logger

__all__ = ["prepare_graceful_restart"]

logger = get_logger(__name__)


def _save_pre_restart_stats() -> None:
    try:
        from src.webui.services.stats import save_stats
        save_stats()
    except Exception as exc:
        logger.debug("重启前保存统计失败: %s", exc)
    try:
        from src.webui.services.request_log import save_requests
        save_requests()
    except Exception as exc:
        logger.debug("重启前保存请求日志失败: %s", exc)


async def _broadcast_restart_notice() -> None:
    try:
        from src.webui.core.logs_ws import log_broker
        await log_broker.broadcast({"type": "system_restarting", "message": "服务正在重启"})
    except Exception as exc:
        logger.debug("重启前广播 WS 失败: %s", exc)


async def _save_terminal_states(registry: Any) -> None:
    try:
        from src.core.server.infra.terminal_sessions import get_terminal_store
        from src.webui.routers.session.terminal import list_sessions
        store = get_terminal_store()
        for session_obj in list_sessions():
            if session_obj._terminal and session_obj.alive:
                session_obj._terminal.save_state(store.persist_dir)
    except Exception as exc:
        logger.debug("重启前保存终端状态失败: %s", exc)


async def prepare_graceful_restart(
    registry: Optional[Any] = None,
    session: Optional[Any] = None,
    *,
    reason: str = "",
) -> None:
    """在触发退出码 42 前持久化状态并关闭长连接。"""
    logger.info("重启前清理%s", f": {reason}" if reason else "")
    _save_pre_restart_stats()
    await _broadcast_restart_notice()
    if registry is not None:
        await _save_terminal_states(registry)
    _ = session
