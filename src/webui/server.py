from __future__ import annotations

"""独立的 WebUI 服务器。"""

import asyncio
import threading
from typing import Any, Optional, Sequence

import aiohttp.web

from src.core.server import ensure_port_available
from src.logger import get_logger
from src.webui.app import create_app

logger = get_logger(__name__)

__all__ = [
    "WebUIServer",
    "ThreadedWebUIServer",
]


class WebUIServer:
    """独立的 WebUI 服务器。"""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8001,
        registry: Optional[Any] = None,
    ) -> None:
        self.host = host
        self.port = port
        self._registry = registry
        self._app = create_app(registry=registry, server=self)
        self._runner: Optional[aiohttp.web.AppRunner] = None
        self._site: Optional[aiohttp.web.TCPSite] = None

    async def reload_app(self) -> None:
        """重建 WebUI 应用。"""
        self._app = create_app(registry=self._registry)
        logger.info("WebUI 应用已热重载")

    async def start(self) -> None:
        """启动服务器。"""
        port_result = ensure_port_available(self.port, False)
        if port_result.occupied:
            raise RuntimeError("WebUI 端口 {} 已被占用: {}".format(self.port, port_result.pids))
        self._runner = aiohttp.web.AppRunner(self._app)
        await self._runner.setup()
        self._site = aiohttp.web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()
        logger.info("WebUI 服务器已启动: http://%s:%d", self.host, self.port)

    async def shutdown(self) -> None:
        """关闭服务器。"""
        if self._runner is None:
            return
        await self._runner.cleanup()
        self._runner = None
        self._site = None
        logger.info("WebUI 服务器已关闭")


class ThreadedWebUIServer:
    """在线程中运行 WebUI。"""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8001,
        registry: Optional[Any] = None,
    ) -> None:
        self.host = host
        self.port = port
        self._registry = registry
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._server: Optional[WebUIServer] = None
        self._startup_error: Optional[BaseException] = None
        self._startup_event = threading.Event()

    @property
    def is_running(self) -> bool:
        """是否正在运行。"""
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        """启动独立线程。"""
        if self.is_running:
            return
        self._startup_error = None
        self._startup_event.clear()
        self._thread = threading.Thread(target=self._run, name="provider-webui", daemon=True)
        self._thread.start()
        self._startup_event.wait(5.0)
        if self._startup_error is not None:
            raise RuntimeError(str(self._startup_error))
        logger.info("WebUI 独立线程已启动")

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            self._server = WebUIServer(host=self.host, port=self.port, registry=self._registry)
            loop.run_until_complete(self._server.start())
            self._startup_event.set()
            loop.run_forever()
        except Exception as exc:
            self._startup_error = exc
            self._startup_event.set()
            logger.error("WebUI 独立线程运行失败: %s", exc, exc_info=True)
        finally:
            pending_tasks = [task for task in asyncio.all_tasks(loop) if not task.done()]
            for task in pending_tasks:
                task.cancel()
            if pending_tasks:
                loop.run_until_complete(asyncio.gather(*pending_tasks, return_exceptions=True))
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
            self._loop = None
            self._server = None

    async def reload_app(self, changed_scopes: Sequence[str] | None = None) -> None:
        """在线程事件循环中重建应用。"""
        if changed_scopes and "webui" not in changed_scopes and "bot" not in changed_scopes:
            return
        if self._loop is None or self._server is None or not self._loop.is_running():
            return
        future = asyncio.run_coroutine_threadsafe(self._server.reload_app(), self._loop)
        await asyncio.wrap_future(future)

    async def shutdown(self, timeout: float = 5.0) -> None:
        """关闭线程中的 WebUI。"""
        if self._loop is None or self._server is None:
            return
        future = asyncio.run_coroutine_threadsafe(self._server.shutdown(), self._loop)
        await asyncio.wait_for(asyncio.wrap_future(future), timeout=timeout)
        self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            await asyncio.to_thread(self._thread.join, timeout)
        logger.info("WebUI 线程已关闭")
