from __future__ import annotations

"""openaifm 平台适配器实现。

PlatformAdapter 接口实现，负责初始化、候选项管理、TTS 补全与生命周期。
网络请求下沉至 ``.client``。
"""

import asyncio
from typing import Any, AsyncGenerator, Dict, List, Union

import aiohttp

from src.core.dispatch.candidate import Candidate
from src.core.errors import NotSupportedError
from src.logger import get_logger
from src.platforms.base import PlatformAdapter
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
                logger.debug("openaifm 后台任务取消或失败: %s", exc)
        if self._client is not None:
            await self._client.close()


# 通用别名，供 adapter.py / util.py 统一导出
Adapter = OpenaiFmAdapter
