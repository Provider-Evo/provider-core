from __future__ import annotations

"""Ollama 平台适配器实现。

PlatformAdapter 接口实现，负责初始化、候选项管理、聊天补全与生命周期。
网络请求下沉至 ``.client``。
"""

import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp

from src.core.candidate import Candidate
from src.core.models_cache import ModelsCache
from src.platforms.base import PlatformAdapter
from src.platforms.ollama.core.constants import (
    CAPS,
    FETCH_MODELS_ENABLED,
    MODEL_FETCH_INTERVAL,
    MODELS,
)

logger = logging.getLogger(__name__)


class OllamaAdapter(PlatformAdapter):
    """Ollama 平台适配器。

    负责初始化客户端、管理模型缓存、委托聊天请求。
    """

    def __init__(self) -> None:
        self._client: Any = None
        self._models: List[str] = list(MODELS)
        self._cache: Optional[ModelsCache] = None
        self._init_task: Optional[asyncio.Task] = None
        self._refresh_task: Optional[asyncio.Task] = None

    @property
    def name(self) -> str:
        """返回平台标识。

        Returns:
            平台名称 "ollama"。
        """
        return "ollama"

    @property
    def supported_models(self) -> List[str]:
        """返回当前可用模型列表（动态发现）。

        Returns:
            模型名称列表。
        """
        if self._client is not None:
            return self._client.get_available_models()
        return list(self._models)

    @property
    def default_capabilities(self) -> Dict[str, bool]:
        """返回默认能力字典。

        Returns:
            能力字典，默认仅支持 chat。
        """
        return CAPS

    async def init(self, session: aiohttp.ClientSession) -> None:
        """初始化适配器——立即注册，后台完成服务器发现。

        Args:
            session: aiohttp 会话实例。
        """
        from src.platforms.ollama.core.client import OllamaClient  # noqa: PLC0415

        self._client = OllamaClient()
        self._init_task = asyncio.ensure_future(self._init_immediate(session))
        self._refresh_task = asyncio.ensure_future(self._background_init())

    async def _init_immediate(self, session: aiohttp.ClientSession) -> None:
        """后台完成即时初始化：服务器发现、连接验证。"""
        if self._client is None:
            return
        try:
            await self._client.init_immediate(session)
            self._cache = ModelsCache(
                platform="ollama",
                fallback_models=MODELS,
                fetch_enabled=FETCH_MODELS_ENABLED,
            )
            cached = await self._cache.load()
            if cached:
                self._models = cached
                self._client.update_models(self._models)
        except Exception as exc:
            logger.warning("ollama 即时初始化失败，将在后台重试: %s", exc)

    async def _background_init(self) -> None:
        """后台初始化：等待即时初始化完成后，服务器发现并持续刷新。"""
        # Wait for init_immediate to finish before starting background work
        if self._init_task is not None:
            try:
                await self._init_task
            except Exception:
                pass  # already logged in _init_immediate
        try:
            await self._client.background_setup()
        except Exception as e:
            logger.warning("ollama后台初始化失败: %s", e)

        if self._cache is not None:
            asyncio.ensure_future(
                self._cache.start_refresh_loop(
                    fetch_fn=self.fetch_remote_models,
                    interval=MODEL_FETCH_INTERVAL,
                    on_update=self._on_models_updated,
                )
            )

    async def _on_models_updated(self, models: List[str]) -> None:
        """模型列表更新回调。

        Args:
            models: 新的模型列表。
        """
        self._models = models
        if self._client is not None:
            self._client.update_models(models)
        logger.debug("ollama模型列表已更新: %d个", len(models))

    async def fetch_remote_models(self) -> List[str]:
        """拉取远程模型列表（从已发现的服务器获取）。

        Returns:
            模型名称列表。
        """
        if self._client is None:
            return list(MODELS)
        return self._client.get_available_models()

    async def candidates(self) -> List[Candidate]:
        """返回候选项列表。

        Returns:
            Candidate 实例列表。
        """
        if self._client is None:
            return []
        return await self._client.candidates()

    async def ensure_candidates(self, count: int) -> int:
        """确保候选项数量。

        Args:
            count: 期望的最小候选项数量。

        Returns:
            实际可用的候选项数量。
        """
        if self._client is None:
            return 0
        return await self._client.ensure_candidates(count)

    async def create_embedding(
        self,
        candidate: "Candidate",
        input_data: Union[str, List[str]],
        model: str,
        **kw: Any,
    ) -> Dict[str, Any]:
        if self._client is None:
            raise RuntimeError("OllamaAdapter 未初始化")
        return await self._client.create_embedding(candidate, input_data, model, **kw)

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
        """执行聊天补全，委托给客户端。

        Args:
            candidate: 候选项实例。
            messages: OpenAI 格式的消息列表。
            model: 模型名称。
            stream: 是否流式输出。
            thinking: 是否启用思考模式（Ollama 不支持，忽略）。
            search: 是否启用搜索（Ollama 不支持，忽略）。
            **kw: 额外参数。

        Yields:
            str（文本增量）、dict（usage/tool_calls）或 None。
        """
        if self._client is None:
            raise RuntimeError("OllamaAdapter 未初始化，请先调用 init()")
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
        """关闭适配器。"""
        if self._init_task is not None and not self._init_task.done():
            self._init_task.cancel()
            try:
                await self._init_task
            except asyncio.CancelledError:
                logger.debug("ollama init task cancelled")
        if self._refresh_task is not None and not self._refresh_task.done():
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                logger.debug("ollama refresh task cancelled")
        if self._client is not None:
            await self._client.close()


# 通用别名，供 adapter.py / util.py 统一导出
Adapter = OllamaAdapter
