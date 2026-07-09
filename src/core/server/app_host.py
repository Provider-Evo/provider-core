from __future__ import annotations

"""aiohttp 应用宿主 — 支持 L3 路由级热重载（替换 AppRunner）。"""

import asyncio
from typing import Any, Optional

import aiohttp.web

from src.logger import get_logger

from src.core.server.app import create_app
from src.core.server.infra.reload.internal.connection_drain import close_live_connections

__all__ = ["AppHost"]

logger = get_logger(__name__)

_RUNNER_SHUTDOWN_TIMEOUT_S = 3.0
_RELOAD_TEARDOWN_TIMEOUT_S = 8.0


class AppHost:
    """管理 aiohttp AppRunner / TCPSite，并提供无进程重启的应用热重载。"""

    def __init__(
        self,
        host: str,
        port: int,
        registry: Any,
        session: Any,
        *,
        access_log: Any = None,
    ) -> None:
        self._host = host
        self._port = port
        self._registry = registry
        self._session = session
        self._access_log = access_log
        self._app: Optional[aiohttp.web.Application] = None
        self._runner: Optional[aiohttp.web.AppRunner] = None
        self._site: Optional[aiohttp.web.TCPSite] = None
        self._reload_lock = asyncio.Lock()

    @property
    def app(self) -> Optional[aiohttp.web.Application]:
        """公开方法 app。"""
        return self._app

    async def start(self) -> None:
        """创建应用并绑定端口。"""
        self._app = await create_app(self._registry, self._session)
        self._runner = aiohttp.web.AppRunner(
            self._app,
            access_log=self._access_log,
            shutdown_timeout=_RUNNER_SHUTDOWN_TIMEOUT_S,
        )
        await self._runner.setup()
        self._site = aiohttp.web.TCPSite(self._runner, self._host, self._port)
        await self._site.start()

    async def reload_app(self) -> None:
        """L3 热重载：排空长连接后重建 Runner。

        runner.cleanup() 默认最多等待 shutdown_timeout 秒让活跃 handler 结束。
        若不先关闭 WebSocket / 流式连接，会在 file watcher 回调超时内卡住，
        导致站点已 stop 但新 Runner 未起来（1337 不可达）。
        """
        async with self._reload_lock:
            if self._runner is None or self._site is None:
                raise RuntimeError("AppHost 尚未启动")

            logger.info("正在热重载应用路由 (L3)...")
            old_runner = self._runner
            old_site = self._site
            self._runner = None
            self._site = None

            await close_live_connections()

            try:
                await asyncio.wait_for(
                    self._teardown_runner(old_site, old_runner),
                    timeout=_RELOAD_TEARDOWN_TIMEOUT_S,
                )
            except Exception as exc:
                logger.error("L3 停止旧 Runner 失败 (%s)，回退进程重启", exc)
                await self._fallback_process_restart("L3 teardown failed")
                return

            try:
                self._app = await create_app(self._registry, self._session)
                self._runner = aiohttp.web.AppRunner(
                    self._app,
                    access_log=self._access_log,
                    shutdown_timeout=_RUNNER_SHUTDOWN_TIMEOUT_S,
                )
                await self._runner.setup()
                self._site = aiohttp.web.TCPSite(self._runner, self._host, self._port)
                await self._site.start()
            except Exception as exc:
                logger.error("L3 重建 Runner 失败 (%s)，回退进程重启", exc)
                await self._fallback_process_restart("L3 rebuild failed")
                return

            logger.info("应用路由热重载完成")

    async def _teardown_runner(
        self,
        site: aiohttp.web.TCPSite,
        runner: aiohttp.web.AppRunner,
    ) -> None:
        await site.stop()
        await runner.cleanup()

    async def _fallback_process_restart(self, reason: str) -> None:
        from src.core.server.infra.reload.internal.pre_restart import prepare_graceful_restart
        from src.core.server.infra.reload.restart import request_graceful_restart

        await prepare_graceful_restart(self._registry, self._session, reason=reason)
        await request_graceful_restart(reason=reason)

    async def shutdown(self) -> None:
        """停止站点并清理 Runner。"""
        await close_live_connections()
        if self._site is not None:
            await self._site.stop()
            self._site = None
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
        self._app = None
