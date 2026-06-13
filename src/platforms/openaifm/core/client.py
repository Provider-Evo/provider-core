from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp

from src.core.candidate import Candidate, make_id
from src.core.errors import NotSupportedError
from ..accounts import API_KEYS
from .constants import BASE_URL, GENERATE_PATH
from .headers import build_headers
from .tts import (
    DEFAULT_STYLE,
    DEFAULT_VOICE,
    STYLE_PROMPTS,
    VOICES,
    build_tts_form_data,
)

logger = logging.getLogger(__name__)
MAX_RETRIES: int = 3


class OpenaiFmClient:
    """openaifm HTTP client coordinator."""

    def __init__(self) -> None:
        """Initialize client."""
        self._session: Optional[aiohttp.ClientSession] = None

    async def init(self, session: aiohttp.ClientSession) -> None:
        """Initialize client, save session.

        Args:
            session: Shared aiohttp ClientSession.
        """
        self._session = session
        logger.info("openaifm 初始化完成")

    async def candidates(self) -> List[Candidate]:
        """Build candidates from credentials.

        Returns:
            List of candidates.
        """
        from .constants import CAPS, MODELS

        return [
            Candidate(
                id=make_id("openaifm", (key or "openaifm")[:12]),
                platform="openaifm",
                resource_id=(key or "openaifm")[:12],
                models=MODELS,
                meta={"api_key": key},
                **CAPS,
            )
            for key in API_KEYS
        ]

    async def ensure_candidates(self, count: int) -> int:
        """Return available candidate count.

        Args:
            count: Expected candidate count.

        Returns:
            Actual candidate count.
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
        """openaifm does not support chat completion.

        Args:
            candidate: Candidate.
            messages: Message list.
            model: Model name.
            stream: Whether streaming.
            thinking: Enable thinking.
            search: Enable search.
            **kw: Extra parameters.

        Yields:
            Nothing; raises NotSupportedError.
        """
        raise NotSupportedError("openaifm 不支持 chat 补全")

    async def create_speech(
        self,
        candidate: Candidate,
        input_text: str,
        model: str,
        voice: str,
        **kw: Any,
    ) -> bytes:
        """Execute speech synthesis with retries.

        Args:
            candidate: Candidate.
            input_text: Input text.
            model: Model name.
            voice: Voice name.
            **kw: Extra parameters.

        Returns:
            Audio bytes.
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
                    "openaifm 重试 %d/%d: %s", attempt + 1, MAX_RETRIES, exc
                )
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("openaifm 未知错误")

    async def _do_tts(
        self,
        candidate: Candidate,
        text: str,
        voice: str,
    ) -> bytes:
        """Call openaifm TTS API.

        Args:
            candidate: Candidate.
            text: Synthesis text.
            voice: Voice name.

        Returns:
            Audio bytes.
        """
        if self._session is None:
            raise RuntimeError("openaifm session 未初始化")
        selected_voice = voice or DEFAULT_VOICE
        if selected_voice not in VOICES:
            selected_voice = DEFAULT_VOICE
        style = DEFAULT_STYLE
        prompt = STYLE_PROMPTS.get(style, "")
        headers = build_headers(candidate.meta.get("api_key", ""))
        form_data = build_tts_form_data(text, prompt, selected_voice, "")
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
            content = await resp.read()
            return content

    async def close(self) -> None:
        """Close client (session managed externally)."""
        return
