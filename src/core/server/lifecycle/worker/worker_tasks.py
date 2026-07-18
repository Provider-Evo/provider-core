from __future__ import annotations

"""Worker 后台任务创建与线程池释放。"""

import asyncio
import os
from typing import Optional

import aiohttp

from src.core.dispatch.engine.registry import Registry
from src.core.server import AutoUpdater
from src.core.server.lifecycle.app.app_host import AppHost
from src.core.server.reload import HotReloadService
from src.core.server.reload.internal.runtime_state import set_hot_reload_service
from src.foundation.logger import get_logger

__all__ = [
    "create_background_tasks",
    "release_default_executor",
    "abort_default_executor",
]

logger = get_logger(__name__)


def _is_idle_worker_env() -> bool:
    from src.core.server.lifecycle.worker import is_idle

    # Runner 子进程的 stdout 为 PIPE，不能用 is_idle() 判定 IDLE 环境。
    return is_idle() and os.environ.get("WORKER_PROCESS") != "1"


async def create_background_tasks(
    cfg: object,
    registry: Registry,
    session: aiohttp.ClientSession,
    app_host: AppHost,
    stop_event: asyncio.Event,
    root: object,
    config_manager: object,
) -> "tuple[list[asyncio.Task], Optional[HotReloadService]]":
    """创建并启动后台异步任务（单 FileWatcher 多订阅）。"""
    is_idle_env = _is_idle_worker_env()
    hot_reload = HotReloadService(
        root,
        registry,
        session,
        app_host,
        config_manager,
        dry_run=is_idle_env,
    )

    async def _hot_reload_task() -> None:
        await hot_reload.start()
        await stop_event.wait()
        await hot_reload.stop()

    async def _autoupdate_task() -> None:
        updater = AutoUpdater(
            root=root,
            branch=cfg.autoupdate.branch,
            interval=cfg.autoupdate.interval,
        )
        await updater.run()

    set_hot_reload_service(hot_reload)

    tasks: list[asyncio.Task] = [
        asyncio.ensure_future(_hot_reload_task()),
    ]

    if cfg.autoupdate.enabled and not is_idle_env:
        tasks.append(asyncio.ensure_future(_autoupdate_task()))

    return tasks, hot_reload


async def release_default_executor() -> None:
    """非阻塞释放默认线程池，避免 asyncio 关停阶段 join 300 秒。"""
    loop = asyncio.get_running_loop()
    executor = loop._default_executor if hasattr(loop, "_default_executor") else None
    if executor is None:
        return
    try:
        executor.shutdown(wait=False, cancel_futures=True)
    except Exception as exc:
        logger.debug("关闭默认线程池失败: %s", exc)
    loop._default_executor = None


def abort_default_executor(loop: asyncio.AbstractEventLoop) -> None:
    """同步丢弃事件循环默认线程池（run_worker finally 兜底）。"""
    executor = loop._default_executor if hasattr(loop, "_default_executor") else None
    if executor is None:
        return
    try:
        executor.shutdown(wait=False, cancel_futures=True)
    except Exception:
        pass
    loop._default_executor = None
