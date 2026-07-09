from __future__ import annotations

"""AItianhu2 平台 PlatformAdapter 接口实现。

本模块承接 :class:`Adapter`（对外别名 :class:`Aitianhu2Adapter`）的完整
实现：初始化 / 候选项管理 / 聊天补全 / 图片生成 / 生命周期关闭。
网络请求下沉至 :mod:`.client`，本层只负责 PlatformAdapter 契约。
"""

import asyncio
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp

from src.logger import get_logger
from src.platforms.base import PlatformAdapter

from .constants import CAPS, MODELS
from .client import Aitianhu2Client

logger = get_logger(__name__)


class Adapter(PlatformAdapter):
    """AItianhu2 平台适配器。"""

    def __init__(self) -> None:
        self._client: Optional[Aitianhu2Client] = None
        self._models: List[str] = list(MODELS)
        self._init_task: Optional[asyncio.Task] = None
        self._bg_task: Optional[asyncio.Task] = None

    @property
    def name(self) -> str:
        """平台标识名。"""
        return "aitianhu2"

    @property
    def supported_models(self) -> List[str]:
        """支持的模型列表。"""
        return list(self._models)

    @property
    def default_capabilities(self) -> Dict[str, bool]:
        """默认能力字典。"""
        return dict(CAPS)

    @property
    def context_length(self) -> Optional[int]:
        """上下文长度。"""
        return 128000

    async def init(self, session: aiohttp.ClientSession) -> None:
        """初始化适配器。"""
        self._client = Aitianhu2Client()
        self._init_task = asyncio.ensure_future(
            self._client.init_immediate(session)
        )
        self._bg_task = asyncio.ensure_future(
            self._client.background_setup()
        )
        logger.info("AItianhu2 适配器初始化已启动")

    async def candidates(self) -> List[Any]:
        """返回当前可用候选项列表。"""
        if self._client is None:
            return []
        return await self._client.candidates()

    async def ensure_candidates(self, count: int) -> int:
        """确保至少有 count 个候选项可用。"""
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
        """聊天补全。"""
        if self._client is None:
            raise RuntimeError("AItianhu2: 客户端未初始化")
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

    async def create_image(
        self,
        candidate: Any,
        prompt: str,
        model: str,
        **kw: Any,
    ) -> Dict[str, Any]:
        """图片生成。"""
        if self._client is None:
            raise RuntimeError("AItianhu2: 客户端未初始化")
        image_prompt = "生成一张图片：{}".format(prompt)
        messages = [{"role": "user", "content": image_prompt}]
        image_data_list: List[str] = []
        async for chunk in self._client.complete(
            candidate,
            messages,
            model,
            stream=False,
            system_hints=["picture_v2"],
        ):
            if isinstance(chunk, str) and "[Image generated:" in chunk:
                start = chunk.find("[Image generated: ") + len("[Image generated: ")
                end = chunk.find("]", start)
                if start > len("[Image generated: ") and end > start:
                    inner = chunk[start:end]
                    if inner.startswith("data:image/png;base64,"):
                        image_data_list.append(inner[len("data:image/png;base64,"):])
        return {
            "created": int(time.time()),
            "data": [{"b64_json": data} for data in image_data_list],
        }

    async def close(self) -> None:
        """关闭适配器。"""
        for task in (self._init_task, self._bg_task):
            if task is not None and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logger.debug("AItianhu2 后台任务已取消")
        if self._client is not None:
            await self._client.close()

    def is_proxy_allowed(self) -> bool:
        """此平台禁止代理切换。"""
        return False

    def is_proxy_enabled(self) -> bool:
        """始终返回 False。"""
        return False

    def set_proxy_enabled(self, enabled: bool, *, auto: bool = False) -> None:
        """无操作。"""
        del enabled, auto
        return None


Aitianhu2Adapter = Adapter
