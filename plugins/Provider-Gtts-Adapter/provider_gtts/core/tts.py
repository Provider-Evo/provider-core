from __future__ import annotations

"""gTTS TTS 参数构造与服务逻辑。"""

from typing import Any, Dict, List, Optional

import aiohttp

from src.core.dispatch.candidate import Candidate
from src.logger import get_logger
from .constants import (
    GTTS_DEFAULT_LANG,
    GTTS_MAX_CHARS,
    GTTS_SLOW,
    MAX_RETRIES,
    TTS_PATH,
    BASE_URL,
)
from .headers import build_headers


def build_tts_params(text: str, lang: str, slow: bool) -> Dict[str, str]:
    """构建 gTTS 查询参数。

    Args:
        text: 待合成文本。
        lang: 语言代码。
        slow: 是否慢速。

    Returns:
        URL 查询参数字典。
    """
    return {
        "ie": "UTF-8",
        "client": "tw-ob",
        "q": text,
        "tl": lang,
        "ttsspeed": "0.24" if slow else "1",
        "total": "1",
        "idx": "0",
        "textlen": str(len(text)),
    }


def split_text(text: str, max_chars: int = GTTS_MAX_CHARS) -> List[str]:
    """按最大长度拆分文本。

    Args:
        text: 待拆分文本。
        max_chars: 每段最大字符数。

    Returns:
        文本片段列表。
    """
    if len(text) <= max_chars:
        return [text]
    parts: List[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        parts.append(text[start:end])
        start = end
    return parts


class TtsService:
    """gTTS 语音合成服务。

    通过构造函数注入 session 与 proxy_resolver。
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        proxy_resolver: Any = None,
    ) -> None:
        """初始化 TTS 服务。

        Args:
            session: 共享的 aiohttp ClientSession。
            proxy_resolver: 代理解析回调（gTTS 通常不需要）。
        """
        self._session = session
        self._resolve_proxy = proxy_resolver

    async def synthesize(
        self,
        candidate: Candidate,
        input_text: str,
        lang: str = GTTS_DEFAULT_LANG,
        slow: bool = GTTS_SLOW,
    ) -> bytes:
        """执行语音合成，包含分片与重试。

        Args:
            candidate: 候选项。
            input_text: 输入文本。
            lang: 语言代码。
            slow: 是否慢速。

        Returns:
            合成后的音频字节。
        """
        chunks = split_text(input_text)
        audio_parts: List[bytes] = []
        for chunk in chunks:
            audio_parts.append(await self._retry_tts(candidate, chunk, lang, slow))
        return b"".join(audio_parts)

    async def _retry_tts(
        self,
        candidate: Candidate,
        text: str,
        lang: str,
        slow: bool,
    ) -> bytes:
        """带重试地请求单段 TTS。

        Args:
            candidate: 候选项。
            text: 文本片段。
            lang: 语言代码。
            slow: 是否慢速。

        Returns:
            音频字节。

        Raises:
            RuntimeError: 全部重试失败后抛出。
        """
        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                import asyncio
                await asyncio.sleep(1.0 * (2 ** (attempt - 1)))
            try:
                return await self._do_tts(candidate, text, lang, slow)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                get_logger(__name__).warning(
                    "gtts 重试 %d/%d: %s", attempt + 1, MAX_RETRIES, exc
                )
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("gtts 未知错误")

    async def _do_tts(
        self,
        candidate: Candidate,
        text: str,
        lang: str,
        slow: bool,
    ) -> bytes:
        """调用 gTTS 端点。

        Args:
            candidate: 候选项。
            text: 文本片段。
            lang: 语言代码。
            slow: 是否慢速。

        Returns:
            音频字节数据。

        Raises:
            RuntimeError: HTTP 请求失败时抛出。
        """
        headers = build_headers(candidate.meta.get("api_key", ""))
        params = build_tts_params(text, lang, slow)
        url = "{}{}".format(BASE_URL, TTS_PATH)
        post_kwargs: Dict[str, Any] = {
            "params": params,
            "headers": headers,
            "ssl": False,
            "timeout": aiohttp.ClientTimeout(connect=10, total=120),
        }
        proxy = self._resolve_proxy() if self._resolve_proxy else None
        if proxy is not None:
            post_kwargs["proxy"] = proxy
        async with self._session.get(url, **post_kwargs) as resp:
            if resp.status != 200:
                body_preview = await resp.text()
                raise RuntimeError(
                    "gtts HTTP {}: {}".format(resp.status, body_preview[:200])
                )
            return await resp.read()
