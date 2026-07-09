from __future__ import annotations

"""热重载协调器 — 分类并调度 L0–L4（debounce 由 FileWatcher 负责）。"""

import asyncio
from pathlib import Path
from typing import Any, Optional, Set

from echotools.logger.manager import get_logger

from src.core.server.infra.reload.classifier import ClassifyResult, classify_paths
from src.core.server.infra.reload.internal.pre_restart import prepare_graceful_restart
from src.core.server.infra.reload.restart import request_graceful_restart

__all__ = ["ReloadCoordinator"]

logger = get_logger(__name__)

_EXECUTE_TIMEOUT_S = 30.0


class ReloadCoordinator:
    """接收文件变更路径，分类并调度 L0–L4 热重载动作。"""

    def __init__(
        self,
        registry: Any,
        session: Any,
        app_host: Any,
        *,
        dry_run: bool = False,
    ) -> None:
        self._registry = registry
        self._session = session
        self._app_host = app_host
        self._dry_run = dry_run
        self._execute_lock = asyncio.Lock()

    async def handle_changes(self, paths: Set[str]) -> None:
        """接收一批文件变更并执行热重载。"""
        if not paths:
            return
        async with self._execute_lock:
            try:
                await asyncio.wait_for(
                    self._execute(paths),
                    timeout=_EXECUTE_TIMEOUT_S,
                )
            except asyncio.TimeoutError:
                logger.error("热重载执行超时 (%ss)", _EXECUTE_TIMEOUT_S)

    async def _execute(self, paths: Set[str]) -> None:
        names = [Path(p).name for p in paths]
        result = classify_paths(paths)
        logger.info("热重载分类 %s -> %s", names, result)

        if self._dry_run:
            self._log_idle_hint(names, result)
            return

        if result.process:
            await request_graceful_restart(
                reason="core 或启动文件变更: {}".format(", ".join(names)),
            )
            return

        if result.platforms:
            await self._reload_platforms(result.platforms)

        if result.application:
            await self._reload_application(names)

        if result.static:
            await self._notify_static_changed(names)

    async def _reload_platforms(self, platforms: frozenset[str]) -> None:
        await self._registry.reload_platforms(sorted(platforms), self._session)

    async def _reload_application(self, names: list[str]) -> None:
        if self._app_host is None:
            await request_graceful_restart(
                reason="应用路由变更但 AppHost 不可用: {}".format(", ".join(names)),
            )
            return
        try:
            await self._app_host.reload_app()
        except Exception as exc:
            logger.error("应用热重载失败，回退进程重启: %s", exc, exc_info=True)
            await prepare_graceful_restart(
                self._registry,
                self._session,
                reason="应用热重载失败",
            )
            await request_graceful_restart(reason="应用热重载失败")

    async def _notify_static_changed(self, names: list[str]) -> None:
        logger.info("前端静态资源变更: %s", names)
        try:
            from src.webui.core.logs_ws import log_broker

            await log_broker.broadcast(
                {
                    "type": "static_changed",
                    "files": names,
                    "message": "前端静态资源已更新，请手动刷新页面",
                },
            )
        except Exception as exc:
            logger.debug("静态资源变更通知失败: %s", exc)

    @staticmethod
    def _log_idle_hint(names: list[str], result: ClassifyResult) -> None:
        logger.info("IDLE 检测到文件变更: %s -> %s", names, result)
        print(
            "\n*** IDLE 文件变更 {}，请手动重启 (python main.py) ***\n".format(names),
            flush=True,
        )
