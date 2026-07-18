"""
app_host 模块。

本文件为 Provider-Evo 项目标准模块，使用以下约定：

- 模块路径：provider-self.src.core.server.lifecycle.app.app_host
- 文件名：app_host.py
- 父包：provider-self/src/core/server/lifecycle/app

职责：

    作为 provider / 核心子系统的标准模块入口；
    通常被 ``plugin.py`` 或上层 ``client.py`` 通过显式 import 使用。

对外接口：

    本模块的 ``__all__`` 列出对外可导入的符号集合；其他内部符号
    可能在重构中调整，调用方应只依赖 ``__all__`` 暴露的稳定 API。

集成：

    - SDK 入口：``plugin.py`` 中 ``create_plugin()`` 引用本模块以构造 platform adapter。
    - 入口路由：``provider-self/src/routes/openai`` 通过 ``from src.core...`` 间接使用。
    - 测试：本目录下的 ``tests/`` 子目录覆盖本模块的核心逻辑。

依赖：

    - 仅依赖 ``provider-sdk`` 与 Python 3.8+ 标准库；不引入第三方 HTTP 库。
    - 不直接读环境变量；所有配置走 ``config/main_config.toml``。

修改指引：

    - 调整本模块时同步更新 ``docs-src/plugins/<name>.md`` 与对应 ``tests/``。
    - 保持单文件 200-400 行；超长请拆为子包并通过 ``__init__.py`` 重新导出。
    - 严禁放置 placeholder / 兜底 / 伪装通过的代码（见 ``AGENTS.md`` Hard Constraints）。
"""


import asyncio
from typing import Any, Optional

import aiohttp.web

from src.foundation.logger import get_logger

from src.core.server.lifecycle.app.app import create_app
from src.core.server.reload.internal.connection_drain import close_live_connections

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
            restart_reason = await self._reload_teardown_and_rebuild(old_site, old_runner)

        if restart_reason is not None:
            await self._fallback_process_restart(restart_reason)

    async def _reload_teardown_and_rebuild(
        self,
        old_site: aiohttp.web.TCPSite,
        old_runner: aiohttp.web.AppRunner,
    ) -> Optional[str]:
        """停止旧 Runner 并重建新 Runner，失败时返回回退重启原因。"""
        try:
            await asyncio.wait_for(
                self._teardown_runner(old_site, old_runner),
                timeout=_RELOAD_TEARDOWN_TIMEOUT_S,
            )
        except Exception as exc:
            logger.error("L3 停止旧 Runner 失败 (%s)，回退进程重启", exc)
            return "L3 teardown failed"

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
            return "L3 rebuild failed"

        logger.info("应用路由热重载完成")
        return None

    async def _teardown_runner(
        self,
        site: aiohttp.web.TCPSite,
        runner: aiohttp.web.AppRunner,
    ) -> None:
        await site.stop()
        await runner.cleanup()

    async def _fallback_process_restart(self, reason: str) -> None:
        from src.core.server.reload.restart import request_process_restart

        await request_process_restart(
            registry=self._registry,
            session=self._session,
            reason=reason,
        )

    def abandon_runner(self) -> None:
        """超时或强制退出时丢弃 Runner 引用，避免关停协程被取消后仍持有站点。"""
        self._site = None
        self._runner = None
        self._app = None

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
