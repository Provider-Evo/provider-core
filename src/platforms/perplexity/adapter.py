from __future__ import annotations

import logging
from typing import Any, AsyncGenerator, Dict, List, Union

import aiohttp

from src.core.candidate import Candidate
from src.platforms.base import PlatformAdapter
from src.platforms.perplexity.client import PerplexityClient

logger = logging.getLogger(__name__)


class PerplexityAdapter(PlatformAdapter):
    """Perplexity 平台适配器。

    使用公共通道（免 API key），支持聊天与搜索/thinking，单候选 public 资源。
    """

    def __init__(self) -> None:
        self._client: PerplexityClient | None = None

    @property
    def name(self) -> str:
        return "perplexity"

    async def init(self, session: aiohttp.ClientSession) -> None:
        self._client = PerplexityClient()
        await self._client.init(session)

    async def candidates(self) -> List[Candidate]:
        if not self._client:
            return []
        return await self._client.candidates()

    async def ensure_candidates(self, count: int) -> int:
        if not self._client:
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
        search: bool = True,
        **kw: Any,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        if not self._client:
            raise RuntimeError("Perplexity adapter not initialized")
        async for chunk in self._client.complete(
            candidate,
            messages,
            model,
            stream,
            thinking=thinking,
            search=search,
            **kw,
        ):
            yield chunk

    async def close(self) -> None:
        if self._client:
            await self._client.close()
