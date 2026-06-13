from __future__ import annotations

"""gTTS HTTP 协调器。

职责限定为协调：账号 / 候选项 / 会话生命周期 /
顶层错误处理与重试。具体业务下放给服务模块。
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import aiohttp

from src.core.candidate import Candidate, make_id
from ..accounts import API_KEYS
from .constants import CAPS, MODELS
from .tts import TtsService

logger = logging.getLogger(__name__)


class Client:
    """gTTS HTTP 协调器。"""

    def __init__(self) -> None:
        """初始化协调器。"""
        self._session: Optional[aiohttp.ClientSession] = None
        self._candidates: List[Candidate] = []
        self._bg_tasks: List[asyncio.Task] = []
        self._closing: bool = False
        # 子服务在 init_immediate() 中实例化
        self._tts: Optional[TtsService] = None

    async def init_immediate(self, session: aiohttp.ClientSession) -> None:
        """立即执行的初始化。

        Args:
            session: 共享的 aiohttp ClientSession。
        """
        self._session = session
        self._rebuild_candidates()
        self._build_services(session)
        logger.info("gtts 初始化完成")

    def _build_services(self, session: aiohttp.ClientSession) -> None:
        """构建子服务实例。

        Args:
            session: 共享的 aiohttp ClientSession。
        """
        self._tts = TtsService(
            session=session,
            proxy_resolver=self._get_proxy_kwarg,
        )

    def _get_proxy_kwarg(self) -> Optional[str]:
        """返回代理 URL 或 None（gTTS 通常不使用代理）。

        Returns:
            代理 URL 或 None。
        """
        return None

    def _rebuild_candidates(self) -> None:
        """根据当前账号状态重建候选项列表。"""
        self._candidates = [
            Candidate(
                id=make_id("gtts", (key or "gtts")[:12]),
                platform="gtts",
                resource_id=(key or "gtts")[:12],
                models=list(MODELS),
                meta={"api_key": key},
                **CAPS,
            )
            for key in API_KEYS
        ]

    async def candidates(self) -> List[Candidate]:
        """返回候选列表。

        Returns:
            候选项列表。
        """
        return list(self._candidates)

    async def ensure_candidates(self, count: int) -> int:
        """确保候选数量。

        Args:
            count: 期望候选数量。

        Returns:
            实际候选数量。
        """
        return len(API_KEYS)

    async def create_speech(
        self,
        candidate: Candidate,
        input_text: str,
        model: str,
        voice: str,
        **kw: Any,
    ) -> bytes:
        """语音合成委托给 TTS 服务。

        Args:
            candidate: 候选项。
            input_text: 输入文本。
            model: 模型名。
            voice: 声音名（保留参数）。
            **kw: 额外参数。

        Returns:
            音频字节。

        Raises:
            RuntimeError: 客户端未初始化时抛出。
        """
        if self._tts is None:
            raise RuntimeError("gtts 客户端未初始化")
        return await self._tts.synthesize(candidate, input_text)

    async def close(self) -> None:
        """关闭客户端，取消后台任务。"""
        self._closing = True
        for task in self._bg_tasks:
            task.cancel()
        for task in self._bg_tasks:
            try:
                await task
            except asyncio.CancelledError:
                logger.debug("gtts 后台任务已取消")
