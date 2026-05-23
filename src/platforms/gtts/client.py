from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp

from src.core.candidate import Candidate, make_id
from src.core.errors import NotSupportedError
from src.platforms.gtts.accounts import API_KEYS
from src.platforms.gtts.util import (
    BASE_URL,
    GTTS_DEFAULT_LANG,
    GTTS_MAX_CHARS,
    GTTS_SLOW,
    TTS_PATH,
    build_headers,
    build_payload,
    build_tts_params,
)

logger = logging.getLogger(__name__)
MAX_RETRIES: int = 3


class GttsClient:
    """gTTS HTTP 客户端。"""

    def __init__(self) -> None:
        """初始化客户端。"""
        self._session: Optional[aiohttp.ClientSession] = None

    async def init(self, session: aiohttp.ClientSession) -> None:
        """初始化客户端，存储 session。

        Args:
            session: 共享的 aiohttp ClientSession。
        """
        self._session = session
        logger.info("gtts 初始化完成")

    async def candidates(self) -> List[Candidate]:
        """构建候选列表。

        Returns:
            候选项列表。
        """
        from src.platforms.gtts.adapter import CAPS, MODELS

        return [
            Candidate(
                id=make_id("gtts"),
                platform="gtts",
                resource_id=(key or "gtts")[:12],
                models=MODELS,
                meta={"api_key": key},
                **CAPS,
            )
            for key in API_KEYS
        ]

    async def ensure_candidates(self, count: int) -> int:
        """返回候选数量。

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
        """gTTS 不支持聊天补全。

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
        raise NotSupportedError("gtts 不支持 chat 补全")

    async def create_speech(
        self,
        candidate: Candidate,
        input_text: str,
        model: str,
        voice: str,
        **kw: Any,
    ) -> bytes:
        """执行语音合成，包含分片与重试。

        Args:
            candidate: 候选项。
            input_text: 输入文本。
            model: 模型名。
            voice: 声音名（保留参数）。
            **kw: 额外参数。

        Returns:
            合成后的音频字节。
        """
        chunks = self._split_text(input_text)
        audio_parts: List[bytes] = []
        for chunk in chunks:
            audio_parts.append(await self._retry_tts(candidate, chunk))
        return b"".join(audio_parts)

    def _split_text(self, text: str) -> List[str]:
        """按最大长度拆分文本。

        Args:
            text: 待拆分文本。

        Returns:
            文本片段列表。
        """
        if len(text) <= GTTS_MAX_CHARS:
            return [text]
        parts: List[str] = []
        start = 0
        while start < len(text):
            end = min(len(text), start + GTTS_MAX_CHARS)
            parts.append(text[start:end])
            start = end
        return parts

    async def _retry_tts(self, candidate: Candidate, text: str) -> bytes:
        """带重试地请求单段 TTS。

        Args:
            candidate: 候选项。
            text: 文本片段。

        Returns:
            音频字节。
        """
        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                await asyncio.sleep(1.0 * (2 ** (attempt - 1)))
            try:
                return await self._do_tts(candidate, text)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning("gtts 重试 %d/%d: %s", attempt + 1, MAX_RETRIES, exc)
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("gtts 未知错误")

    async def _do_tts(self, candidate: Candidate, text: str) -> bytes:
        """调用 gTTS 端点。

        Args:
            candidate: 候选项。
            text: 文本片段。

        Returns:
            音频字节数据。
        """
        if self._session is None:
            raise RuntimeError("gtts session 未初始化")
        headers = build_headers(candidate.meta.get("api_key", ""))
        params = build_tts_params(text, GTTS_DEFAULT_LANG, GTTS_SLOW)
        url = "{}{}".format(BASE_URL, TTS_PATH)
        async with self._session.get(
            url,
            params=params,
            headers=headers,
            ssl=False,
            timeout=aiohttp.ClientTimeout(connect=10, total=120),
        ) as resp:
            if resp.status != 200:
                body_preview = await resp.text()
                raise RuntimeError(
                    "gtts HTTP {}: {}".format(resp.status, body_preview[:200])
                )
            return await resp.read()

    async def close(self) -> None:
        """关闭客户端（session 由外部管理）。"""
        return
