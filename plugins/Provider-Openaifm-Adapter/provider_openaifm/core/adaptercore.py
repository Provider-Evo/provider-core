"""
adaptercore 模块。

本文件为 Provider-Evo 项目标准模块，使用以下约定：

- 模块路径：provider-plugin.Provider-Openaifm-Adapter.provider_openaifm.core.adaptercore
- 文件名：adaptercore.py
- 父包：provider-plugin/Provider-Openaifm-Adapter/provider_openaifm/core

职责：

    作为 SDK 兼容入口，转发到 ``provider_*.core`` 下的真实实现层。
    此模式让 ``from provider_xxx import adapter`` 与 ``from provider_xxx.adapter import …``
    同时可用，无需调用方关心内部布局。

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
from typing import Any, AsyncGenerator, Dict, List, Union

import aiohttp

from src.core.dispatch.cand import Candidate
from src.core.utils.errors import NotSupportedError
from src.foundation.logger import get_logger
from provider_sdk.extensions.platform.adapter import PlatformAdapter
from .constants import CAPS, MODELS

logger = get_logger(__name__)


class OpenaiFmAdapter(PlatformAdapter):
    """openaifm platform adapter."""

    def __init__(self) -> None:
        """Initialize adapter."""
        self._client: Any = None
        self._task: Any = None

    @property
    def name(self) -> str:
        """Platform identifier name.

        Returns:
            Platform name string.
        """
        return "openaifm"

    @property
    def supported_models(self) -> List[str]:
        """Supported model list.

        Returns:
            Model name list.
        """
        return MODELS

    @property
    def default_capabilities(self) -> Dict[str, bool]:
        """Default capabilities dict.

        Returns:
            Capabilities dict.
        """
        return CAPS

    async def init(self, session: aiohttp.ClientSession) -> None:
        """Initialize adapter, start background task.

        Args:
            session: Shared aiohttp ClientSession.
        """
        from .client import OpenaiFmClient  # noqa: PLC0415

        self._client = OpenaiFmClient()
        self._task = asyncio.ensure_future(self._client.init(session))

    async def candidates(self) -> List[Candidate]:
        """Return candidate list.

        Returns:
            List of candidates.
        """
        if self._client is None:
            return []
        return await self._client.candidates()

    async def ensure_candidates(self, count: int) -> int:
        """Ensure candidate count.

        Args:
            count: Expected candidate count.

        Returns:
            Actual available candidate count.
        """
        if self._client is None:
            return 0
        return await self._client.ensure_candidates(count)

    async def complete(
        self,
        candidate: Candidate,
        messages: List[Dict[str, Any]],
        model: str,
        stream: bool,
        *,
        thinking: bool = False,
        search: bool = False,
        **kw: Any,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """Openaifm does not provide chat completion.

        Args:
            candidate: Candidate.
            messages: Message list.
            model: Model name.
            stream: Whether streaming.
            thinking: Enable thinking.
            search: Enable search.
            **kw: Extra parameters.

        Yields:
            Nothing; raises NotSupportedError.
        """
        raise NotSupportedError("openaifm 不支持 chat 补全")

    async def create_speech(
        self,
        candidate: Candidate,
        input_text: str,
        model: str,
        voice: str,
        **kw: Any,
    ) -> bytes:
        """Delegate speech synthesis to client implementation.

        Args:
            candidate: Candidate.
            input_text: Input text.
            model: Model name.
            voice: Voice name.
            **kw: Extra parameters.

        Returns:
            Audio bytes.
        """
        if self._client is None:
            raise RuntimeError("openaifm 客户端未初始化")
        return await self._client.create_speech(candidate, input_text, model, voice, **kw)

    async def close(self) -> None:
        """Close adapter, clean up background tasks."""
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception) as exc:
                logger.warning("openaifm 后台任务取消或失败: %s", exc)
        if self._client is not None:
            await self._client.close()


# 通用别名，供 adapter.py / util.py 统一导出
Adapter = OpenaiFmAdapter

# =======================================================================
# 重导出 — 同包内协同模块的公共符号（保持外部 ``from .. import`` 路径稳定）
# =======================================================================

from .headers import (
    build_headers,
)

__all__ = [
    "build_headers",
]

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
