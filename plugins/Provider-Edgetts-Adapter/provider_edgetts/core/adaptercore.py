"""Edge TTS 适配器实现。"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator, Dict, List

import aiohttp

from src.core.dispatch.candidate import Candidate
from src.core.errors import NotSupportedError
from src.logger import get_logger
from src.platforms.base import PlatformAdapter
from .client import Client
from .constants import CAPS, MODELS

logger = get_logger(__name__)


class EdgeTtsAdapter(PlatformAdapter):
    """Edge TTS 平台适配器实现。"""

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
        return "edgetts"

    @property
    def supported_models(self) -> List[str]:
        """支持的模型列表。

        Returns:
            模型名列表。
        """
        return MODELS

    @property
    def default_capabilities(self) -> Dict[str, bool]:
        """默认能力字典。

        Returns:
            能力字典。
        """
        return CAPS

    async def init(self, session: aiohttp.ClientSession) -> None:
        """初始化适配器，立即返回，后台 Task 完成实际初始化。

        Args:
            session: 共享的 aiohttp ClientSession。
        """
        self._client = Client()
        self._init_task = asyncio.ensure_future(
            self._client.init_immediate(session)
        )
        self._bg_task = asyncio.ensure_future(
            self._client.background_setup()
        )

    async def candidates(self) -> List[Candidate]:
        """返回当前可用候选项列表。

        Returns:
            候选项列表。
        """
        if self._client is None:
            return []
        return self._client.get_candidates()

    async def ensure_candidates(self, count: int) -> int:
        """确保候选项数量。

        Args:
            count: 期望的候选数量。

        Returns:
            实际可用的候选数量。
        """
        if self._client is None:
            return 0
        return self._client.ensure_candidates(count)

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
    ) -> AsyncGenerator[Any, None]:
        """聊天补全（edge tts 不支持）。

        Args:
            candidate: 候选项。
            messages: 消息列表。
            model: 模型名。
            stream: 是否流式。
            thinking: 是否启用 thinking。
            search: 是否启用搜索。
            **kw: 额外参数。

        Raises:
            NotSupportedError: 始终抛出，因为 TTS 不支持聊天补全。
        """
        raise NotSupportedError("edgetts 不支持 chat 补全")

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
            voice: 声音名称。
            **kw: 额外参数。

        Returns:
            合成后的音频字节。
        """
        if self._client is None:
            raise RuntimeError("edgetts 客户端未初始化")
        return await self._client.create_speech(candidate, input_text, model, voice, **kw)

    async def close(self) -> None:
        """关闭适配器，取消后台任务。"""
        for task in (self._init_task, self._bg_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logger.debug("edgetts 后台任务已取消")
        if self._client is not None:
            await self._client.close()


Adapter = EdgeTtsAdapter
