from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp

from src.core.dispatch.candidate import Candidate, make_id
from src.core.errors import NotSupportedError
from src.logger import get_logger
from .constants import BASE_URL, CAPS, GENERATE_PATH, MODELS, VOICES
from .headers import build_headers
from .tts import (
    DEFAULT_STYLE,
    DEFAULT_VOICE,
    STYLE_PROMPTS,
    build_tts_form_data,
)

logger = get_logger(__name__)
MAX_RETRIES: int = 3


class OpenaiFmClient:
    """openaifm HTTP 客户端。"""

    def __init__(self) -> None:
        self._session: Optional[aiohttp.ClientSession] = None
        self._candidates: List[Candidate] = []

    async def init(self, session: aiohttp.ClientSession) -> None:
        """初始化客户端。"""
        self._session = session
        self._rebuild_candidates()
        logger.debug("openaifm 初始化完成，候选项: %d 个", len(self._candidates))

    def _rebuild_candidates(self) -> None:
        """构建候选项（单候选项，无需认证，不依赖 accounts.py）。"""
        self._candidates = [
            Candidate(
                id=make_id("openaifm", "openaifm"),
                platform="openaifm",
                resource_id="openaifm",
                models=list(MODELS),
                meta={},
                **CAPS,
            )
        ]

    async def candidates(self) -> List[Candidate]:
        """返回候选项列表。"""
        return list(self._candidates)

    async def ensure_candidates(self, count: int) -> int:
        """返回可用候选项数量。"""
        return len(self._candidates)

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
        """openaifm 不支持 chat 补全。"""
        raise NotSupportedError("openaifm 不支持 chat 补全")

    async def create_speech(
        self,
        candidate: Candidate,
        input_text: str,
        model: str,
        voice: str,
        **kw: Any,
    ) -> bytes:
        """执行语音合成，含指数退避重试。

        Args:
            candidate: 候选项。
            input_text: 合成文本。
            model: 模型名（openaifm 中用作 voice）。
            voice: 声音名称。
            **kw: 额外参数（支持 prompt/vibe）。

        Returns:
            音频字节。
        """
        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                await asyncio.sleep(1.0 * (2 ** (attempt - 1)))
            try:
                return await self._do_tts(
                    input_text, voice or model, kw
                )
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "openaifm 重试 %d/%d: %s", attempt + 1, MAX_RETRIES, exc
                )
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("openaifm 未知错误")

    async def _do_tts(
        self,
        text: str,
        voice: str,
        kw: Dict[str, Any],
    ) -> bytes:
        """调用 openaifm TTS API。

        Args:
            text: 合成文本。
            voice: 声音名称。
            kw: 额外参数（prompt, vibe）。

        Returns:
            音频字节。
        """
        if self._session is None:
            raise RuntimeError("openaifm session 未初始化")

        selected_voice = voice if voice in VOICES else DEFAULT_VOICE
        style = kw.get("style", DEFAULT_STYLE)
        prompt = kw.get("prompt") or STYLE_PROMPTS.get(style, "")
        vibe = kw.get("vibe", "")

        headers = build_headers()
        form_data = build_tts_form_data(text, prompt, selected_voice, vibe)

        async with self._session.post(
            BASE_URL + GENERATE_PATH,
            data=form_data,
            headers=headers,
            ssl=False,
            timeout=aiohttp.ClientTimeout(connect=10, total=300),
        ) as resp:
            if resp.status != 200:
                body_preview = await resp.text()
                raise RuntimeError(
                    "openaifm HTTP {}: {}".format(resp.status, body_preview[:200])
                )
            return await resp.read()

    async def close(self) -> None:
        """清理资源（session 由外部管理）。"""
        return
