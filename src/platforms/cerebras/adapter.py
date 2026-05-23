"""Cerebras 平台适配器"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp

from src.core.candidate import Candidate
from src.core.models_cache import ModelsCache
from src.platforms.base import PlatformAdapter

logger = logging.getLogger(__name__)

# 硬编码模型列表——兜底，始终存在
MODELS: List[str] = [
    "gpt-oss-120b",
    "llama-3.3-70b",
    "llama-4-maverick-17b-128e-instruct",
    "llama-4-scout-17b-16e-instruct",
    "llama3.1-8b",
    "qwen-3-235b-a22b-instruct-2507",
    "qwen-3-235b-a22b-thinking-2507",
    "qwen-3-32b",
    "qwen-3-coder-480b",
]

# 能力字典——Cerebras 支持 chat 和 tools
CAPS: Dict[str, bool] = {
    "chat": True,
    "tools": True,
}

# 是否允许用远程模型列表覆盖本地（Cerebras SDK 可查询模型列表）
FETCH_MODELS_ENABLED: bool = False

# 远程模型刷新间隔（秒），默认 24 小时
MODEL_FETCH_INTERVAL: int = 86400


class CerebrasAdapter(PlatformAdapter):
    """Cerebras 平台适配器。

    使用官方 cerebras-cloud-sdk 同步 SDK，通过 ThreadPoolExecutor 桥接异步。
    初始化立即返回，后台任务处理模型列表拉取。
    """

    def __init__(self) -> None:
        self._client: Any = None
        self._models: List[str] = list(MODELS)
        self._cache: Optional[ModelsCache] = None
        self._refresh_task: Optional[asyncio.Task] = None

    @property
    def name(self) -> str:
        """返回平台标识符。"""
        return "cerebras"

    @property
    def supported_models(self) -> List[str]:
        """返回当前支持的模型列表副本。"""
        return list(self._models)

    @property
    def default_capabilities(self) -> Dict[str, bool]:
        """返回平台默认能力字典。"""
        return CAPS

    async def init(self, session: aiohttp.ClientSession) -> None:
        """初始化适配器——立即注册，后台完善。

        Args:
            session: 共享的 aiohttp ClientSession（Cerebras 使用 SDK，不直接使用 session）。
        """
        from src.platforms.cerebras.client import CerebrasClient

        self._client = CerebrasClient()
        # 立即初始化，不阻塞
        await self._client.init_immediate(session)
        # 加载模型缓存
        self._cache = ModelsCache(
            platform="cerebras",
            fallback_models=MODELS,
            fetch_enabled=FETCH_MODELS_ENABLED,
        )
        cached = await self._cache.load()
        if cached:
            self._models = cached
            self._client.update_models(self._models)
        # 启动后台任务
        self._refresh_task = asyncio.ensure_future(self._background_init())

    async def _background_init(self) -> None:
        """后台初始化：完成耗时操作后持续刷新。"""
        try:
            await self._client.background_setup()
        except Exception as e:
            logger.warning("cerebras 后台初始化失败: %s", e)
        # 启动模型定时刷新
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
        logger.info("cerebras 模型列表已更新: %d 个", len(models))

    async def fetch_remote_models(self) -> List[str]:
        """拉取远程模型列表，委托给 client。

        Returns:
            从 Cerebras API 获取的模型 ID 列表，失败时返回硬编码列表。
        """
        if self._client is None:
            return list(MODELS)
        return await self._client.fetch_remote_models()

    async def candidates(self) -> List[Candidate]:
        """返回当前可用候选项。

        Returns:
            当前所有有效候选项列表。
        """
        if self._client is None:
            return []
        return await self._client.candidates()

    async def ensure_candidates(self, count: int) -> int:
        """确保候选项数量。

        Args:
            count: 期望的候选项数量。

        Returns:
            实际可用的候选项数量。
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
        """聊天补全，委托给 client。

        Args:
            candidate: 选中的候选项。
            messages: 对话消息列表。
            model: 模型名称。
            stream: 是否流式输出。
            thinking: 是否启用推理模式（Cerebras 暂不支持）。
            search: 是否启用搜索（Cerebras 暂不支持）。
            **kw: 其他透传参数。

        Yields:
            str 类型的文本片段，或 dict 类型的 usage 信息。
        """
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
        if self._refresh_task is not None and not self._refresh_task.done():
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                logger.debug("cerebras refresh task cancelled")
        if self._client is not None:
            await self._client.close()
