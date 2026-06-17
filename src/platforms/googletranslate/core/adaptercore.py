"""Google Translate 翻译平台适配器实现。

``PlatformAdapter`` 接口实现，负责初始化、候选项管理与聊天补全（翻译）。
网络请求下沉至 ``.client``。

翻译映射到 chat/completions 接口：
- system 消息 = 源语言代码（如 "en", "zh-CN", "ja"）
- user 消息 = 待翻译文本
- assistant 响应 = 翻译后的文本
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp

from src.core.candidate import Candidate
from src.platforms.base import PlatformAdapter
from .constants import (
    CAPS,
    MODELS,
)

logger = logging.getLogger(__name__)


class GoogleTranslateAdapter(PlatformAdapter):
    """Google Translate 翻译平台适配器。"""

    def __init__(self) -> None:
        """初始化适配器。"""
        self._client: Any = None
        self._models: List[str] = list(MODELS)

    @property
    def name(self) -> str:
        """返回平台标识。"""
        return "googletranslate"

    @property
    def supported_models(self) -> List[str]:
        """返回当前支持的模型列表。"""
        return list(self._models)

    @property
    def default_capabilities(self) -> Dict[str, bool]:
        """返回默认能力字典。"""
        return CAPS

    async def init(self, session: aiohttp.ClientSession) -> None:
        """初始化适配器——立即返回。

        Args:
            session: 共享 aiohttp 会话。
        """
        from .client import GoogleTranslateClient  # noqa: PLC0415

        self._client = GoogleTranslateClient()
        await self._client.init_immediate(session)

    async def candidates(self) -> List[Candidate]:
        """返回当前可用候选项。"""
        if self._client is None:
            return []
        return await self._client.candidates()

    async def ensure_candidates(self, count: int) -> int:
        """确保候选项数量。"""
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
        """翻译补全——提取文本，调用 Google Translate API，返回翻译结果。"""
        async for chunk in self._client.complete(
            candidate,
            messages,
            model,
            stream,
            **kw,
        ):
            yield chunk

    async def close(self) -> None:
        """关闭适配器，释放资源。"""
        if self._client is not None:
            await self._client.close()


Adapter = GoogleTranslateAdapter
