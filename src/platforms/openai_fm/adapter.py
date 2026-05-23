from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, List, Union

import aiohttp

from src.core.candidate import Candidate
from src.core.errors import NotSupportedError
from src.platforms.base import PlatformAdapter

logger = logging.getLogger(__name__)

MODELS: List[str] = [
    "tts-1",
    "tts-1-hd",
    "alloy",
    "ash",
    "ballad",
    "coral",
    "echo",
    "fable",
    "onyx",
    "nova",
    "sage",
    "shimmer",
    "verse",
]
CAPS: Dict[str, bool] = {
    "audio_gen": True,
}


class OpenaiFmAdapter(PlatformAdapter):
    """openai_fm 平台适配器。"""

    def __init__(self) -> None:
        """初始化适配器。"""
        self._client: Any = None
        self._task: Any = None

    @property
    def name(self) -> str:
        """平台标识名。

        Returns:
            平台名字符串。
        """
        return "openai_fm"

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
        """初始化适配器，启动后台任务。

        Args:
            session: 共享的 aiohttp ClientSession。
        """
        from src.platforms.openai_fm.client import OpenaiFmClient

        self._client = OpenaiFmClient()
        self._task = asyncio.ensure_future(self._client.init(session))

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
            count: 期望的候选数量。

        Returns:
            实际可用的候选数量。
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
        """OpenAI.fm 不提供聊天补全。

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
        raise NotSupportedError("openai_fm 不支持 chat 补全")

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
        """
        if self._client is None:
            raise RuntimeError("openai_fm 客户端未初始化")
        return await self._client.create_speech(candidate, input_text, model, voice, **kw)

    async def close(self) -> None:
        """关闭适配器，清理后台任务。"""
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        if self._client is not None:
            await self._client.close()
