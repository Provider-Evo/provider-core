"""
adaptercore 模块。

本文件为 Provider-Evo 项目标准模块，使用以下约定：

- 模块路径：provider-plugin.Provider-Gtts-Adapter.provider_gtts.core.adaptercore
- 文件名：adaptercore.py
- 父包：provider-plugin/Provider-Gtts-Adapter/provider_gtts/core

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
from .client import Client

logger = get_logger(__name__)


class GttsAdapter(PlatformAdapter):
    """gTTS 平台适配器。"""

    def __init__(self) -> None:
        """初始化适配器。"""
        self._client: Any = None
        self._init_task: Any = None
        self._bg_task: Any = None

    @property
    def name(self) -> str:
        """平台标识名。

        Returns:
            平台名字符串。
        """
        return "gtts"

    @property
    def supported_models(self) -> List[str]:
        """支持的模型列表。

        Returns:
            模型名列表。
        """
        return list(MODELS)

    @property
    def default_capabilities(self) -> Dict[str, bool]:
        """默认能力字典。

        Returns:
            能力字典。
        """
        return dict(CAPS)

    async def init(self, session: aiohttp.ClientSession) -> None:
        """初始化适配器，立即返回；后台 Task 完成客户端初始化。

        Args:
            session: 共享的 aiohttp ClientSession。
        """
        self._client = Client()
        self._init_task = asyncio.ensure_future(
            self._client.init_immediate(session)
        )

    async def candidates(self) -> List[Candidate]:
        """返回候选列表。

        Returns:
            候选项列表。
        """
        if self._client is None:
            return []
        return await self._client.candidates()

    async def ensure_candidates(self, count: int) -> int:
        """确保候选数量。

        Args:
            count: 期望候选数量。

        Returns:
            实际候选数量。
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
        """gTTS 不支持聊天补全。

        Args:
            candidate: 候选项。
            messages: 消息列表。
            model: 模型名。
            stream: 是否流式。
            thinking: 是否启用 thinking。
            search: 是否启用搜索。
            **kw: 额外参数。

        Yields:
            不会产生输出，直接抛出不支持异常。
        """
        raise NotSupportedError("gtts 不支持 chat 补全")

    async def create_speech(
        self,
        candidate: Candidate,
        input_text: str,
        model: str,
        voice: str,
        **kw: Any,
    ) -> bytes:
        """语音合成委托客户端实现。

        Args:
            candidate: 候选项。
            input_text: 输入文本。
            model: 模型名。
            voice: 声音名。
            **kw: 额外参数。

        Returns:
            音频字节。

        Raises:
            RuntimeError: 客户端未初始化时抛出。
        """
        if self._client is None:
            raise RuntimeError("gtts 客户端未初始化")
        return await self._client.create_speech(candidate, input_text, model, voice, **kw)

    async def close(self) -> None:
        """关闭适配器，取消后台任务。"""
        for task in (self._init_task, self._bg_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logger.debug("gtts 适配器后台任务已取消")
        if self._client is not None:
            await self._client.close()


Adapter = GttsAdapter

# =======================================================================
# 重导出 — 同包内协同模块的公共符号（保持外部 ``from .. import`` 路径稳定）
# =======================================================================

from .headers import (
    build_headers,
)

from .payloads import (
    build_payload,
)

__all__ = [
    "build_headers",
    "build_payload",
]
