from __future__ import annotations

"""aiohttp 应用宿主 — 支持 L3 路由级热重载（替换 AppRunner）。"""

import asyncio
from typing import Any, Optional

import aiohttp.web

from src.foundation.logger import get_logger

from src.core.server.lifecycle.app import create_app
from src.core.server.infra.reload.internal.connection_drain import close_live_connections

__all__ = ["AppHost"]

logger = get_logger(__name__)

_RUNNER_SHUTDOWN_TIMEOUT_S = 3.0
_RELOAD_TEARDOWN_TIMEOUT_S = 8.0
_SHUTDOWN_LOCK_WAIT_S = 2.0
_SHUTDOWN_STEP_TIMEOUT_S = 3.0


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

        进程级回退重启须在释放 ``_reload_lock`` 之后触发，否则 Worker 关停
        会在 ``shutdown()`` 中永久等待该锁。
        """
        restart_reason: str | None = None

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
                restart_reason = "L3 teardown failed"
            else:
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
                    restart_reason = "L3 rebuild failed"
                else:
                    logger.info("应用路由热重载完成")

        if restart_reason is not None:
            await self._fallback_process_restart(restart_reason)

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
        lock_acquired = False
        try:
            await asyncio.wait_for(
                self._reload_lock.acquire(),
                timeout=_SHUTDOWN_LOCK_WAIT_S,
            )
            lock_acquired = True
        except asyncio.TimeoutError:
            logger.warning(
                "热重载仍在进行，跳过锁等待并强制关停 Web 服务器",
            )

        try:
            await close_live_connections()
            if self._site is not None:
                await asyncio.wait_for(
                    self._site.stop(),
                    timeout=_SHUTDOWN_STEP_TIMEOUT_S,
                )
                self._site = None
            if self._runner is not None:
                await asyncio.wait_for(
                    self._runner.cleanup(),
                    timeout=_SHUTDOWN_STEP_TIMEOUT_S,
                )
                self._runner = None
            self._app = None
        finally:
            if lock_acquired:
                self._reload_lock.release()
