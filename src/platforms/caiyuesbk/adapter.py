"""caiyuesbk 平台适配器"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp

from src.core.candidate import Candidate
from src.core.models_cache import ModelsCache
from src.platforms.base import PlatformAdapter

logger = logging.getLogger(__name__)

# 硬编码兜底模型列表
MODELS: List[str] = [
    "Qwen3-32B-siliconflow",
    "glm-4.6-siliconflow",
    "qwen3-80b",
    "kimi-k2",
    "kimi-k2-thinking",
    "deepseek-v3.1-terminus",
    "deepseek-v3.1",
    "deepseek-v3.2-siliconflow",
    "glm4.7",
    "kimi-k2-instruct-0905",
    "qwen3.5-122b",
    "gpt-oss-120b",
    "glm-4.6V-siliconflow",
    "kimi-k2-siliconflow",
]

# 能力配置——只声明平台真实支持的能力
CAPS: Dict[str, bool] = {
    "chat": True,
    "tools": True,
    "thinking": True,
    "vision": True,
}

# 是否允许远程模型列表覆盖本地（True=覆盖，False=只增不减）
FETCH_MODELS_ENABLED: bool = True

# 远程模型刷新间隔（秒），默认 24 小时
MODEL_FETCH_INTERVAL: int = 86400


class CaiyuesbkAdapter(PlatformAdapter):
    """caiyuesbk 平台适配器。"""

    def __init__(self) -> None:
        self._client: Any = None
        self._models: List[str] = list(MODELS)
        self._cache: Optional[ModelsCache] = None
        self._refresh_task: Optional[asyncio.Task] = None

    @property
    def name(self) -> str:
        """返回平台唯一标识符。"""
        return "caiyuesbk"

    @property
    def supported_models(self) -> List[str]:
        """返回当前支持的模型列表（实时更新）。"""
        return list(self._models)

    @property
    def default_capabilities(self) -> Dict[str, bool]:
        """返回平台默认能力声明。"""
        return CAPS

    async def init(self, session: aiohttp.ClientSession) -> None:
        """初始化适配器——立即注册，后台完善。

        Args:
            session: 共享的 aiohttp 客户端会话。
        """
        from src.platforms.caiyuesbk.client import CaiyuesbkClient

        self._client = CaiyuesbkClient()
        # 立即注册，不阻塞
        await self._client.init_immediate(session)

        # 加载持久化模型缓存
        self._cache = ModelsCache(
            platform="caiyuesbk",
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
        """后台初始化：完成耗时操作，启动模型定时刷新。"""
        try:
            await self._client.background_setup()
        except Exception as e:
            logger.warning("caiyuesbk 后台初始化失败: %s", e)

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
            models: 最新的模型列表。
        """
        self._models = models
        if self._client is not None:
            self._client.update_models(models)
        logger.info("caiyuesbk 模型列表已更新: %d 个", len(models))

    async def fetch_remote_models(self) -> List[str]:
        """拉取远程模型列表。

        Returns:
            从远程 API 获取的模型 ID 列表，失败时返回硬编码兜底列表。
        """
        if self._client is None:
            return list(MODELS)
        try:
            return await self._client.fetch_models()
        except Exception as e:
            logger.warning("caiyuesbk 拉取远程模型失败: %s", e)
            return list(MODELS)

    async def candidates(self) -> List[Candidate]:
        """返回当前可用候选项列表。"""
        if self._client is None:
            return []
        return await self._client.candidates()

    async def ensure_candidates(self, count: int) -> int:
        """确保候选项数量满足要求。

        Args:
            count: 期望的候选项数量。

        Returns:
            当前实际候选项数量。
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
        """聊天补全，委托给 client 执行。

        Args:
            candidate: 选中的候选项。
            messages: 对话消息列表。
            model: 模型名称。
            stream: 是否流式响应。
            thinking: 是否启用思考模式。
            search: 是否启用搜索增强。
            **kw: 其他透传参数。

        Yields:
            文本增量（str）或元数据字典（dict）。
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
        """关闭适配器，释放所有资源。"""
        if self._refresh_task is not None and not self._refresh_task.done():
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                logger.debug("caiyuesbk refresh task cancelled")
        if self._client is not None:
            await self._client.close()
