from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, List, Union

import aiohttp

from src.core.candidate import Candidate
from src.platforms.base import PlatformAdapter

logger = logging.getLogger(__name__)

# 最小兜底模型（远程拉取失败时使用）
MODELS: List[str] = ["roleplay:free"]

# 能力：仅支持 chat/stream
CAPS: Dict[str, bool] = {
    "chat": True,
}


class ApiairforceAdapter(PlatformAdapter):
    """apiairforce 平台适配器。"""

    def __init__(self) -> None:
        self._client: Any = None
        self._task: Any = None

    @property
    def name(self) -> str:
        return "apiairforce"

    @property
    def supported_models(self) -> List[str]:
        if self._client is not None and getattr(self._client, "_models_cache", None):
            return list(self._client._models_cache)
        return MODELS

    @property
    def default_capabilities(self) -> Dict[str, bool]:
        return CAPS

    async def init(self, session: aiohttp.ClientSession) -> None:
        from src.platforms.apiairforce.client import ApiairforceClient

        self._client = ApiairforceClient()
        self._task = asyncio.ensure_future(self._client.init(session))

    async def candidates(self) -> List[Candidate]:
        if self._client is None:
            return []
        return await self._client.candidates()

    async def ensure_candidates(self, count: int) -> int:
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
        async for chunk in self._client.complete(
            candidate, messages, model, stream, thinking=thinking, search=search, **kw
        ):
            yield chunk

    async def close(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        if self._client is not None:
            await self._client.close()

    async def fetch_remote_models(self) -> List[str]:
        if self._client is None:
            return []
        return await self._client.fetch_remote_models()
