"""
server 模块。

本文件为 Provider-Evo 项目标准模块，使用以下约定：

- 模块路径：provider-self.src.webui.bootstrap.server
- 文件名：server.py
- 父包：provider-self/src/webui/bootstrap

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
import threading
from typing import Any, Optional, Sequence

import aiohttp.web

from src.core.server import ensure_port_available
from src.foundation.logger import get_logger
from src.webui.bootstrap.app import create_app

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
        """重建 WebUI 应用并替换 AppRunner（L3 热重载）。"""
        if self._runner is None or self._site is None:
            raise RuntimeError("WebUI 服务器尚未启动")
        await self._site.stop()
        await self._runner.cleanup()
        self._app = create_app(registry=self._registry, server=self)
        self._runner = aiohttp.web.AppRunner(self._app)
        await self._runner.setup()
        self._site = aiohttp.web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()
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
        if self._site is not None:
            await self._site.stop()
            self._site = None
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
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
            await asyncio.get_running_loop().run_in_executor(None, self._thread.join, timeout)
        logger.info("WebUI 线程已关闭")

# =======================================================================
# 相关模块
# =======================================================================
#
# 同包内协同模块通过 ``from .X import Y`` 重导出，外部调用方无需感知包内布局。
# 若需新增协同模块，请将对应 ``.py`` 文件放在本模块同级目录，并在末尾追加重导出。
#
# 设计原则：
#   1. 每个文件只承担一个明确的职责（单一职责原则）。
#   2. 跨文件依赖只通过显式 import 表达；避免隐式全局状态。
#   3. 公共 API 集中在 ``__all__``；私有符号以下划线开头。
#   4. 模块 docstring 描述用途、依赖、修改指引，作为运行时自描述文档。
#
# 错误处理：
#   - 错误一律 raise，不在底层吞掉（见 ``AGENTS.md`` Hard Constraints）。
#   - 上层 ``plugin.py`` / ``client.py`` 统一处理重试与 fallback。
#
# 测试：
#   - ``tests/`` 子目录覆盖本模块的所有公共函数。
#   - 覆盖率门禁为 90%（见 ``pyproject.toml``）。
#
# 文档：
#   - 用户文档位于 ``docs-src/plugins/``。
#   - 架构决策写入 ``PROJECT_DECISIONS.md``。
#
# 重构策略：
#   - 单文件超过 400 行时，提取子模块并通过 ``__init__.py`` 重导出。
#   - 跨多个 Provider 共享的逻辑抽取至 ``src/core/``；本文件不重复实现。
#
# 兼容：
#   - 旧路径 ``from .module import *`` 仍可用（见 ``__all__``）。
#   - 删除本文件前请先在 ``plugin.py`` 中确认无引用。
#
# 验证：
#   - 修改后运行 ``python -m py_compile`` 确认语法。
#   - 运行 ``pytest tests/`` 确认行为。
#   - 运行 ``python .claude/scripts/check_dir_limit.py`` 确认行数约束。
