"""Zen 平台适配器实现。

PlatformAdapter 接口实现，负责初始化、候选项管理、聊天补全与生命周期。
网络请求下沉至 ``.client``。
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp

from src.core.dispatch.candidate import Candidate
from src.core.models_cache import ModelsCache
from src.logger import get_logger
from src.platforms.base import PlatformAdapter
from .constants import (
    CAPS,
    FETCH_MODELS_ENABLED,
    MODEL_FETCH_INTERVAL,
    MODELS,
)

logger = get_logger(__name__)


class ZenAdapter(PlatformAdapter):
    """Zen平台适配器。"""

    def __init__(self) -> None:
        self._client: Any = None
        self._models: List[str] = list(MODELS)
        self._cache: Optional[ModelsCache] = None
        self._refresh_task: Optional[asyncio.Task] = None

    @property
    def name(self) -> str:
        """返回平台标识。"""
        return "zen"

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
        from .client import ZenClient  # noqa: PLC0415

        self._client = ZenClient()
        await self._client.init_immediate(session)

        self._cache = ModelsCache(
            platform="zen",
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
            logger.warning("zen后台初始化失败: %s", e)

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
        logger.debug("zen模型列表已更新: %d个", len(models))

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

    async def close(self) -> None:
        """关闭适配器，释放资源。"""
        if self._refresh_task is not None and not self._refresh_task.done():
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                logger.debug("zen 刷新任务已取消")
        if self._client is not None:
            await self._client.close()


# 通用别名，供 adapter.py / util.py 统一导出
Adapter = ZenAdapter
