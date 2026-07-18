from __future__ import annotations

"""Worker 优雅关停：终端会话、后台任务、资源释放。"""

import asyncio
from typing import List, Optional

import aiohttp

from src.core.dispatch.engine.registry import Registry
from src.core.server.lifecycle.app.app_host import AppHost
from src.core.server.lifecycle.net.conn import close_shared_connector
from src.core.server.reload import HotReloadService
from src.core.server.reload.internal.connection_drain import close_live_connections
from src.core.utils.compat.observability import get_observability_services
from src.foundation.logger import get_logger

__all__ = ["shutdown_worker"]

logger = get_logger(__name__)

_SHUTDOWN_STEP_TIMEOUT = 5.0


async def _await_shutdown_step(
    awaitable: object,
    *,
    timeout: float,
    step_name: str,
) -> Optional[object]:
    """为关停步骤设置硬超时，避免单个组件阻塞 Ctrl+C 退出。"""
    try:
        return await asyncio.wait_for(awaitable, timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("%s 超时，继续执行后续关停步骤", step_name)
        return None
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.warning("%s 失败，继续执行后续关停步骤: %s", step_name, exc)
        return None


async def _detach_terminal_sessions(sessions: list, timeout: float = 2.0) -> None:
    for session in sessions:
        try:
            await asyncio.wait_for(session.detach_for_shutdown(), timeout=timeout)
        except Exception as exc:
            logger.debug("终端 detach 失败: %s", exc)


async def _close_terminal_sessions(sessions: list, timeout: float = 2.0) -> None:
    for session in sessions:
        terminal = session._terminal if hasattr(session, "_terminal") else None
        if terminal is None:
            continue
        close_fn = terminal.close if hasattr(terminal, "close") else None
        if close_fn is None:
            continue
        try:
            await asyncio.wait_for(close_fn(), timeout=timeout)
        except Exception as exc:
            logger.debug("关闭终端会话失败: %s", exc)


async def _shutdown_terminal_sessions() -> None:
    """关停终端：可配置 preserve_on_shutdown 仅 detach 不 kill。"""
    from src.foundation.config import get_config

    cfg = get_config().terminal
    try:
        get_observability_services().save_terminal_states()
    except Exception as exc:
        logger.debug("保存终端状态失败: %s", exc)

    try:
        from src.webui.routers.session.terminal.session_all.term import list_sessions

        sessions = list(list_sessions())
        if cfg.preserve_on_shutdown:
            await _detach_terminal_sessions(sessions)
            return
        await _close_terminal_sessions(sessions)
    except Exception as exc:
        logger.debug("枚举终端会话失败: %s", exc)


async def _drain_remaining_tasks() -> None:
    """取消并收割事件循环中残留任务，减轻 asyncio.run 退出阶段挂起。"""
    current = asyncio.current_task()
    pending = [
        task
        for task in asyncio.all_tasks()
        if task is not current and not task.done()
    ]
    if not pending:
        return
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)


async def _close_log_sockets() -> None:
    try:
        sockets = await get_observability_services().close_log_sockets()
    except Exception as exc:
        logger.warning("收集日志 WebSocket 失败: %s", exc, exc_info=True)
        sockets = []
    for ws in sockets:
        try:
            await asyncio.wait_for(ws.close(), timeout=1.0)
        except Exception as exc:
            logger.debug("关闭日志 WebSocket 失败: %s", exc)


async def _cancel_background_tasks(
    tasks: List[asyncio.Task],
    hot_reload_service: Optional[HotReloadService],
    reload_callback: Optional[object],
    config_manager: Optional[object],
) -> None:
    logger.info("取消后台任务...")
    for task in tasks:
        task.cancel()
    await _await_shutdown_step(
        asyncio.gather(*tasks, return_exceptions=True),
        timeout=_SHUTDOWN_STEP_TIMEOUT,
        step_name="取消后台任务",
    )

    if hot_reload_service is not None:
        await _await_shutdown_step(
            hot_reload_service.stop(),
            timeout=_SHUTDOWN_STEP_TIMEOUT,
            step_name="停止热重载服务",
        )

    if reload_callback is not None and config_manager is not None:
        try:
            config_manager.unregister_reload_callback(reload_callback)
        except Exception as exc:
            logger.warning("注销配置热重载回调失败: %s", exc, exc_info=True)


async def _close_worker_resources(
    registry: Registry,
    session: aiohttp.ClientSession,
    app_host: AppHost,
) -> None:
    await _await_shutdown_step(
        close_live_connections(),
        timeout=_SHUTDOWN_STEP_TIMEOUT,
        step_name="关闭活动 WebSocket",
    )
    await _await_shutdown_step(
        _shutdown_terminal_sessions(),
        timeout=_SHUTDOWN_STEP_TIMEOUT,
        step_name="关闭终端会话",
    )

    await _close_log_sockets()

    logger.info("正在停止 Web 服务器...")
    await _await_shutdown_step(
        app_host.shutdown(),
        timeout=_SHUTDOWN_STEP_TIMEOUT,
        step_name="停止 Web 服务器",
    )
    app_host.abandon_runner()

    logger.info("正在关闭注册表...")
    await _await_shutdown_step(
        registry.close(),
        timeout=_SHUTDOWN_STEP_TIMEOUT,
        step_name="关闭注册表",
    )

    logger.info("正在关闭 HTTP Session...")
    await _await_shutdown_step(
        session.close(),
        timeout=_SHUTDOWN_STEP_TIMEOUT,
        step_name="关闭 HTTP Session",
    )

    await _await_shutdown_step(
        close_shared_connector(),
        timeout=_SHUTDOWN_STEP_TIMEOUT,
        step_name="关闭 HTTP 连接池",
    )


async def shutdown_worker(
    tasks: List[asyncio.Task],
    registry: Registry,
    session: aiohttp.ClientSession,
    app_host: AppHost,
    hot_reload_service: Optional[HotReloadService] = None,
    *,
    reload_callback: Optional[object] = None,
    config_manager: Optional[object] = None,
) -> None:
    """优雅关闭所有后台任务和资源。"""
    await _cancel_background_tasks(tasks, hot_reload_service, reload_callback, config_manager)
    await _close_worker_resources(registry, session, app_host)

    from src.core.server.lifecycle.worker.worker_tasks import release_default_executor

    await _drain_remaining_tasks()
    await release_default_executor()

    logger.info("Provider-V2 已完全退出")
