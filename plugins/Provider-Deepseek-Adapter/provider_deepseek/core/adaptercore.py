from __future__ import annotations

# src/platforms/deepseek/core/adaptercore.py
"""DeepSeek 平台适配器真实实现"""

import asyncio
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from src.logger import get_logger

import aiohttp

from src.platforms.base import PlatformAdapter
from src.platforms.deepseek.core.constants import (
    CAPS,
    FETCH_MODELS_ENABLED,
    MODEL_FETCH_INTERVAL,
    MODELS,
)
from src.platforms.deepseek.core.modelcache import ModelsCache

logger = get_logger(__name__)


class DeepseekAdapter(PlatformAdapter):
    """DeepSeek 平台适配器（支持 pro/flash/vision 三个模型）。"""

    def __init__(self) -> None:
        """初始化适配器。"""
        # 延迟导入以避免循环依赖，client 模块由 util 汇聚后才稳定
        from src.platforms.deepseek.core.client import DeepseekClient  # noqa: PLC0415

        self._client: Optional[DeepseekClient] = None
        self._models: List[str] = list(MODELS)
        self._cache: Optional[ModelsCache] = None
        self._init_task: Optional[asyncio.Task] = None  # type: ignore[type-arg]
        self._refresh_task: Optional[asyncio.Task] = None  # type: ignore[type-arg]

    @property
    def name(self) -> str:
        """平台标识名。"""
        return "deepseek"

    @property
    def supported_models(self) -> List[str]:
        """当前支持的模型列表。"""
        return list(self._models)

    @property
    def default_capabilities(self) -> Dict[str, bool]:
        """默认能力字典（取两模型能力并集）。"""
        return dict(CAPS)

    @property
    def context_length(self) -> Optional[int]:
        """上下文长度（默认 128k）。"""
        return 131072

    async def init(self, session: aiohttp.ClientSession) -> None:
        """初始化适配器——立即返回，耗时操作交后台 Task。

        Args:
            session: 共享的 aiohttp ClientSession。
        """
        from src.platforms.deepseek.core.client import DeepseekClient  # noqa: PLC0415

        self._client = DeepseekClient()
        self._init_task = asyncio.ensure_future(self._init_immediate(session))
        self._refresh_task = asyncio.ensure_future(self._background_init())

    async def _init_immediate(self, session: aiohttp.ClientSession) -> None:
        """后台完成即时初始化：API 密钥验证、账户登录等。"""
        if self._client is None:
            return
        try:
            await self._client.init_immediate(session)
            self._cache = ModelsCache(
                platform="deepseek",
                fallback_models=MODELS,
                fetch_enabled=FETCH_MODELS_ENABLED,
            )
            cached = await self._cache.load()
            if cached:
                self._models = cached
                self._client.update_models(self._models)
        except Exception as exc:
            logger.warning("deepseek 即时初始化失败，将在后台重试: %s", exc)

    async def _background_init(self) -> None:
        """后台初始化：等待即时初始化完成后，完成耗时操作并持续刷新。"""
        # Wait for init_immediate to finish before starting background work
        if self._init_task is not None:
            try:
                await self._init_task
            except Exception:
                pass  # already logged in _init_immediate
        if self._client is None:
            return
        try:
            await self._client.background_setup()
        except Exception as exc:
            logger.warning("deepseek 后台初始化失败: %s", exc)

        if self._cache is not None:
            asyncio.ensure_future(
                self._cache.start_refresh_loop(
                    fetch_fn=self._fetch_remote_models,
                    interval=MODEL_FETCH_INTERVAL,
                    on_update=self._on_models_updated,
                )
            )

    async def _fetch_remote_models(self) -> List[str]:
        """拉取远程模型列表（DeepSeek 无公开接口，返回硬编码）。"""
        return list(MODELS)

    async def _on_models_updated(self, models: List[str]) -> None:
        """模型列表更新回调。

        Args:
            models: 新的模型列表。
        """
        self._models = models
        if self._client is not None:
            self._client.update_models(models)
        logger.info("deepseek 模型列表已更新: %d 个", len(models))

    async def candidates(self) -> list:
        """返回当前可用候选项。"""
        if self._client is None:
            return []
        return await self._client.candidates()

    async def ensure_candidates(self, count: int) -> int:
        """确保候选项数量。

        Args:
            count: 期望候选项数量。

        Returns:
            当前实际可用数量。
        """
        if self._client is None:
            return 0
        return await self._client.ensure_candidates(count)

    async def complete(
        self,
        candidate: Any,
        messages: List[Dict[str, Any]],
        model: str,
        stream: bool,
        *,
        thinking: bool = False,
        search: bool = False,
        **kw: Any,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """聊天补全，委托给 client。

        Args:
            candidate: 候选项。
            messages: 消息列表。
            model: 模型名。
            stream: 是否流式。
            thinking: 是否启用思考模式（仅 pro/flash 支持）。
            search: 是否启用联网搜索（仅 pro/flash 支持）。
            **kw: 额外参数透传。

        Yields:
            str（文本增量）或 dict（thinking/usage/tool_calls）。
        """
        if self._client is None:
            return
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
        """关闭适配器，释放资源。"""
        if self._init_task is not None and not self._init_task.done():
            self._init_task.cancel()
            try:
                await self._init_task
            except asyncio.CancelledError:
                logger.debug("deepseek init task cancelled")
        if self._refresh_task is not None and not self._refresh_task.done():
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                logger.debug("deepseek refresh task cancelled")
        if self._client is not None:
            await self._client.close()

    def set_proxy_enabled(self, enabled: bool) -> None:
        """设置 DeepSeek 平台的代理覆盖开关。

        只有在配置中允许的平台才能真正生效。

        Args:
            enabled: True 强制使用代理，False 强制不使用。
        """
        if not self.is_proxy_allowed():
            return
        if self._client is not None:
            self._client.set_proxy_enabled(enabled)

    def is_proxy_allowed(self) -> bool:
        """返回 DeepSeek 平台是否被允许使用代理切换。"""
        from src.core.config import get_config
        cfg = get_config()
        return cfg.platforms_proxy.is_platform_enabled(self.name)

    def is_proxy_enabled(self) -> bool:
        """返回 DeepSeek 平台当前是否启用代理覆盖。

        Returns:
            是否启用代理。
        """
        if not self.is_proxy_allowed():
            return False
        if self._client is not None:
            return self._client.is_proxy_enabled()
        return False


Adapter = DeepseekAdapter
