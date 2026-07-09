from __future__ import annotations

"""Perplexity 平台适配器实现。

PlatformAdapter 接口实现，负责初始化、候选项管理、聊天补全与生命周期。
网络请求下沉至 ``.client``。
"""

from typing import Any, AsyncGenerator, Dict, List, Union

import aiohttp

from src.core.dispatch.candidate import Candidate
from src.logger import get_logger
from src.platforms.base import PlatformAdapter
from .client import PerplexityClient
from .constants import CAPS
from .models import MODELS

logger = get_logger(__name__)


class PerplexityAdapter(PlatformAdapter):
    """Perplexity 平台适配器。

    使用公共通道（免 API key），支持聊天与搜索/thinking，单候选 public 资源。
    """

    def __init__(self) -> None:
        self._client: PerplexityClient | None = None

    @property
    def name(self) -> str:
        """Return the platform identifier."""
        return "perplexity"

    @property
    def supported_models(self) -> List[str]:
        """Return supported model list.

        Returns:
            Model name list.
        """
        return list(MODELS)

    @property
    def default_capabilities(self) -> Dict[str, bool]:
        """Return default capabilities dict.

        Returns:
            Capabilities dictionary.
        """
        return dict(CAPS)

    async def init(self, session: aiohttp.ClientSession) -> None:
        """Initialize the adapter with an aiohttp session.

        Args:
            session: The shared aiohttp ClientSession.
        """
        self._client = PerplexityClient()
        await self._client.init(session)

    async def candidates(self) -> List[Candidate]:
        """Return available candidates.

        Returns:
            List of Candidate objects.
        """
        if not self._client:
            return []
        return await self._client.candidates()

    async def ensure_candidates(self, count: int) -> int:
        """Ensure at least `count` candidates are available.

        Args:
            count: Minimum number of candidates expected.

        Returns:
            Actual number of candidates.
        """
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
        """Execute a chat completion request.

        Args:
            candidate: The selected candidate.
            messages: The conversation message list.
            model: The model name.
            stream: Whether to stream the response.
            thinking: Whether to enable thinking mode.
            search: Whether to enable search.
            **kw: Additional keyword arguments passed through.

        Yields:
            Text chunks or data dicts from the response.

        Raises:
            RuntimeError: If the adapter has not been initialized.
        """
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
        """Close the adapter and release resources."""
        if self._client:
            await self._client.close()


# 通用别名，供 adapter.py / util.py 统一导出
Adapter = PerplexityAdapter
