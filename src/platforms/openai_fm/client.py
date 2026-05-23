from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp

from src.core.candidate import Candidate, make_id
from src.core.errors import NotSupportedError
from src.platforms.openai_fm.accounts import API_KEYS
from src.platforms.openai_fm.util import (
    API_ENDPOINT,
    DEFAULT_STYLE,
    DEFAULT_VOICE,
    STYLES,
    STYLE_PROMPTS,
    VOICES,
    build_headers,
    build_payload,
    build_tts_form_data,
)

logger = logging.getLogger(__name__)
MAX_RETRIES: int = 3


class OpenaiFmClient:
    """openai_fm HTTP 客户端。"""

    def __init__(self) -> None:
        """初始化客户端。"""
        self._session: Optional[aiohttp.ClientSession] = None

    async def init(self, session: aiohttp.ClientSession) -> None:
        """初始化客户端，保存 session。

        Args:
            session: 共享的 aiohttp ClientSession。
        """
        self._session = session
        logger.info("openai_fm 初始化完成")

    async def candidates(self) -> List[Candidate]:
        """从凭证构建候选项。

        Returns:
            候选项列表。
        """
        from src.platforms.openai_fm.adapter import CAPS, MODELS

        return [
            Candidate(
                id=make_id("openai_fm"),
                platform="openai_fm",
                resource_id=(key or "openai_fm")[:12],
                models=MODELS,
                meta={"api_key": key},
                **CAPS,
            )
            for key in API_KEYS
        ]

    async def ensure_candidates(self, count: int) -> int:
        """返回可用候选数量。

        Args:
            count: 期望候选数量。

        Returns:
            实际候选数量。
        """
        return len(API_KEYS)

    async def complete(
        self,
        candidate: Candidate,
        messages: List[Dict],
        model: str,
        stream: bool,
        *,
        thinking: bool = False,
        search: bool = False,
        **kw: Any,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """openai.fm 不支持聊天补全。

        Args:
            candidate: 候选项。
            messages: 消息列表。
            model: 模型名。
            stream: 是否流式。
            thinking: 是否启用 thinking。
            search: 是否启用搜索。
            **kw: 额外参数。

        Yields:
            不会产生输出，直接抛出不支持异常。
        """
        raise NotSupportedError("openai_fm 不支持 chat 补全")

    async def create_speech(
        self,
        candidate: Candidate,
        input_text: str,
        model: str,
        voice: str,
        **kw: Any,
    ) -> bytes:
        """执行语音合成，带重试。

        Args:
            candidate: 候选项。
            input_text: 输入文本。
            model: 模型名。
            voice: 声音名。
            **kw: 额外参数。

        Returns:
            音频字节。
        """
        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                await asyncio.sleep(1.0 * (2 ** (attempt - 1)))
            try:
                return await self._do_tts(candidate, input_text, voice)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning(
                    "openai_fm 重试 %d/%d: %s", attempt + 1, MAX_RETRIES, exc
                )
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("openai_fm 未知错误")

    async def _do_tts(
        self,
        candidate: Candidate,
        text: str,
        voice: str,
    ) -> bytes:
        """调用 openai.fm TTS 接口。

        Args:
            candidate: 候选项。
            text: 合成文本。
            voice: 声音名。

        Returns:
            音频字节数据。
        """
        if self._session is None:
            raise RuntimeError("openai_fm session 未初始化")
        selected_voice = voice or DEFAULT_VOICE
        if selected_voice not in VOICES:
            selected_voice = DEFAULT_VOICE
        style = DEFAULT_STYLE
        prompt = STYLE_PROMPTS.get(style, "")
        headers = build_headers(candidate.meta.get("api_key", ""))
        form_data = build_tts_form_data(text, prompt, selected_voice, "")
        async with self._session.post(
            API_ENDPOINT,
            data=form_data,
            headers=headers,
            ssl=False,
            timeout=aiohttp.ClientTimeout(connect=10, total=300),
        ) as resp:
            if resp.status != 200:
                body_preview = await resp.text()
                raise RuntimeError(
                    "openai_fm HTTP {}: {}".format(resp.status, body_preview[:200])
                )
            content = await resp.read()
            return content

    async def close(self) -> None:
        """关闭客户端（session 由外部管理）。"""
        return
