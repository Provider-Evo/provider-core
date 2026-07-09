from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator, Dict, List, Union

import aiohttp

from src.core.dispatch.candidate import Candidate
from src.logger import get_logger
from src.platforms.base import PlatformAdapter
from .client import Client
from .constants import CAPS, MODELS

logger = get_logger(__name__)

__all__ = ["Adapter", "ApiairforceAdapter"]


class Adapter(PlatformAdapter):
    """apiairforce 平台适配器。"""

    def __init__(self) -> None:
        self._client: Client | None = None
        self._init_task: asyncio.Task | None = None

    @property
    def name(self) -> str:
        return "apiairforce"

    @property
    def supported_models(self) -> List[str]:
        if self._client is not None:
            return self._client.supported_models
        return MODELS

    @property
    def default_capabilities(self) -> Dict[str, bool]:
        return CAPS

    async def init(self, session: aiohttp.ClientSession) -> None:
        """立即返回；后台 Task 完成登录等耗时操作。"""
        self._client = Client()
        self._init_task = asyncio.ensure_future(
            self._client.init(session)
        )

    async def candidates(self) -> List[Candidate]:
        """返回当前可用候选项列表。"""
        if self._client is None:
            return []
        return self._client.candidates()

    async def ensure_candidates(self, count: int) -> int:
        """确保候选项数量，返回实际数量。"""
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
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """聊天补全，yield str 或 dict。"""
        if self._client is None:
            return
        async for chunk in self._client.complete(
            candidate, messages, model, stream, thinking=thinking, search=search, **kw
        ):
            yield chunk

    async def close(self) -> None:
        """关闭适配器，取消后台任务。"""
        if self._init_task is not None and not self._init_task.done():
            self._init_task.cancel()
            try:
                await self._init_task
            except (asyncio.CancelledError, Exception) as exc:
                logger.debug("apiairforce 适配器后台任务取消或失败: %s", exc)
        if self._client is not None:
            await self._client.close()

    async def fetch_remote_models(self) -> List[str]:
        """拉取远程模型列表。"""
        if self._client is None:
            return []
        return await self._client.fetch_remote_models()


ApiairforceAdapter = Adapter
