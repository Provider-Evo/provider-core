# src/platforms/openrouter/adapter.py
"""OpenRouter平台适配器"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp

from src.core.candidate import Candidate
from src.core.models_cache import ModelsCache
from src.platforms.base import PlatformAdapter

logger = logging.getLogger(__name__)

MODELS: List[str] = [
    "qwen/qwen3-235b-a22b:free",
    "qwen/qwen3-30b-a3b:free",
    "deepseek/deepseek-r1-0528:free",
    "deepseek/deepseek-chat-v3-0324:free",
    "deepseek/deepseek-r1:free",
    "google/gemini-2.0-flash-exp:free",
    "google/gemini-2.5-flash-preview:free",
    "google/gemini-2.5-flash-preview-05-20:free",
    "google/gemma-3-27b-it:free",
    "google/gemma-3-12b-it:free",
    "google/gemma-3-4b-it:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "meta-llama/llama-3.1-8b-instruct:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
    "microsoft/phi-4:free",
    "microsoft/phi-4-reasoning:free",
    "qwen/qwen3-14b:free",
    "qwen/qwen3-32b:free",
    "qwen/qwen3-8b:free",
    "qwen/qwen3-4b:free",
    "qwen/qwen3-1.7b:free",
    "qwen/qwen3-0.6b:free",
    "qwen/qwen-2.5-72b-instruct:free",
    "qwen/qwq-32b:free",
    "nvidia/llama-3.1-nemotron-70b-instruct:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
]

CAPS: Dict[str, bool] = {
    "chat": True,
    "vision": True,
    "tools": True,
    "thinking": True,
    "search": True,
    "embedding": True,
}

FETCH_MODELS_ENABLED: bool = True
MODEL_FETCH_INTERVAL: int = 86400

RATE_LIMIT_COOLDOWN: int = 30
RECOVERY_INTERVAL: int = 60


class OpenRouterAdapter(PlatformAdapter):
    """OpenRouter平台适配器"""

    def __init__(self) -> None:
        self._client: Any = None
        self._models: List[str] = list(MODELS)
        self._cache: Optional[ModelsCache] = None
        self._refresh_task: Optional[asyncio.Task] = None

    @property
    def name(self) -> str:
        """返回平台标识。"""
        return "openrouter"

    @property
    def supported_models(self) -> List[str]:
        """返回当前支持的模型列表。"""
        return list(self._models)

    @property
    def default_capabilities(self) -> Dict[str, bool]:
        """返回默认能力字典。"""
        return CAPS

    async def init(self, session: aiohttp.ClientSession) -> None:
        """初始化适配器——立即注册，后台完善。"""
        from src.platforms.openrouter.client import OpenRouterClient

        self._client = OpenRouterClient()
        await self._client.init_immediate(session)

        self._cache = ModelsCache(
            platform="openrouter",
            fallback_models=MODELS,
            fetch_enabled=FETCH_MODELS_ENABLED,
        )
        cached = await self._cache.load()
        if cached:
            self._models = cached
            self._client.update_models(self._models)

        self._refresh_task = asyncio.ensure_future(self._background_init())

    async def _background_init(self) -> None:
        """后台初始化：完成耗时操作后持续刷新。"""
        try:
            await self._client.background_setup()
        except Exception as e:
            logger.warning("openrouter后台初始化失败: %s", e)

        if self._cache is not None:
            asyncio.ensure_future(
                self._cache.start_refresh_loop(
                    fetch_fn=self.fetch_remote_models,
                    interval=MODEL_FETCH_INTERVAL,
                    on_update=self._on_models_updated,
                )
            )

    async def _on_models_updated(self, models: List[str]) -> None:
        """模型列表更新回调。"""
        self._models = models
        if self._client is not None:
            self._client.update_models(models)
        logger.info("openrouter模型列表已更新: %d个", len(models))

    async def fetch_remote_models(self) -> List[str]:
        """拉取远程模型列表，委托给client。"""
        if self._client is None:
            return list(MODELS)
        return await self._client.fetch_remote_models()

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
        """聊天补全，委托给client。"""
        async for chunk in self._client.complete(
            candidate, messages, model, stream,
            thinking=thinking, search=search, **kw,
        ):
            yield chunk

    async def embed(
        self,
        candidate: Candidate,
        input_data: Union[str, List[str]],
        model: str,
    ) -> Dict[str, Any]:
        """计算嵌入，委托给client。"""
        if not self._client:
            from src.core.errors import UnsupportedServiceError
            raise UnsupportedServiceError("openrouter客户端未初始化")
        return await self._client.embed(candidate, input_data, model)

    async def close(self) -> None:
        """关闭适配器，释放资源。"""
        if self._refresh_task is not None and not self._refresh_task.done():
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
        if self._client is not None:
            await self._client.close()
