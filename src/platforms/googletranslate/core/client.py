"""Google Translate HTTP 客户端。

负责翻译请求，使用硬编码公共 API Key，无需账号管理。
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp

from echotools.translate import extract_text_from_messages, split_text_chunks

from src.core.candidate import Candidate, make_id
from src.core.errors import PlatformError
from .constants import (
    API_KEY,
    BASE_URL,
    CAPS,
    DEFAULT_SOURCE_LANG,
    DEFAULT_TARGET_LANG,
    MODELS,
    RATE_LIMIT_COOLDOWN,
    RECOVERY_INTERVAL,
    TRANSLATE_PATH,
)

logger = logging.getLogger(__name__)
MAX_RETRIES: int = 3


class GoogleTranslateClient:
    """Google Translate HTTP 客户端。"""

    def __init__(self) -> None:
        """初始化客户端。"""
        self._session: Optional[aiohttp.ClientSession] = None
        self._valid: bool = True
        self._rate_limit_until: float = 0.0
        self._last_error_time: float = 0.0

    async def init_immediate(self, session: aiohttp.ClientSession) -> None:
        """立即初始化。

        Args:
            session: 共享 aiohttp 会话。
        """
        self._session = session
        logger.debug("googletranslate 客户端初始化完成 (公共 API Key)")

    @property
    def _available(self) -> bool:
        """判断是否可用。"""
        if not self._valid:
            if time.time() - self._last_error_time >= RECOVERY_INTERVAL:
                self._valid = True
            else:
                return False
        if self._rate_limit_until > time.time():
            return False
        return True

    async def candidates(self) -> List[Candidate]:
        """单个候选项（公共 API，无需按 Key 管理）。"""
        if not self._available:
            return []
        return [
            Candidate(
                id=make_id("googletranslate", "public"),
                platform="googletranslate",
                resource_id="public",
                models=list(MODELS),
                context_length=None,
                meta={},
                **CAPS,
            )
        ]

    async def ensure_candidates(self, count: int) -> int:
        """返回可用数量（0 或 1）。"""
        return 1 if self._available else 0

    async def complete(
        self,
        candidate: Candidate,
        messages: List[Dict[str, Any]],
        model: str,
        stream: bool,
        **kw: Any,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """执行翻译请求，含重试逻辑。

        Args:
            candidate: 候选项。
            messages: 消息列表。
            model: 模型名（忽略）。
            stream: 是否流式返回。
            **kw: 额外参数，支持 target_lang / source_lang 覆盖。
        """
        target_lang = kw.get("target_lang", DEFAULT_TARGET_LANG)
        source_lang_override = kw.get("source_lang", "")

        text, msg_source, _target = extract_text_from_messages(messages)
        source_lang = source_lang_override or msg_source or DEFAULT_SOURCE_LANG

        if not text or not text.strip():
            yield ""
            return

        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                await asyncio.sleep(1.0 * (2 ** (attempt - 1)))
            try:
                async for chunk in self._do_request(
                    text, source_lang, target_lang, stream,
                ):
                    yield chunk
                return
            except PlatformError as e:
                last_exc = e
                logger.warning(
                    "googletranslate 重试 %d/%d: %s",
                    attempt + 1,
                    MAX_RETRIES,
                    e,
                )
            except Exception as e:
                last_exc = e
                logger.warning(
                    "googletranslate 重试 %d/%d: %s",
                    attempt + 1,
                    MAX_RETRIES,
                    e,
                )
        if last_exc:
            raise last_exc

    async def _do_request(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        stream: bool,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """执行单次 Google Translate 请求。

        Args:
            text: 待翻译文本。
            source_lang: 源语言代码。
            target_lang: 目标语言代码。
            stream: 是否流式返回。
        """
        url = "{}{}".format(BASE_URL, TRANSLATE_PATH)
        headers = {
            "X-Goog-Api-Key": API_KEY,
            "Content-Type": "application/json",
        }

        # Google Translate API body: [[["text"], "srclang", "tgtlang"], "wt_lib"]
        body = [
            [[text], source_lang if source_lang != "auto" else "auto", target_lang],
            "wt_lib",
        ]

        try:
            async with self._session.post(
                url,
                headers=headers,
                json=body,
                ssl=False,
                timeout=aiohttp.ClientTimeout(connect=10, total=60),
            ) as resp:
                if resp.status != 200:
                    body_text = await resp.text()
                    self._last_error_time = time.time()
                    if resp.status == 429:
                        self._rate_limit_until = time.time() + RATE_LIMIT_COOLDOWN
                    raise PlatformError(
                        "googletranslate HTTP{}: {}".format(
                            resp.status, body_text[:200]
                        )
                    )

                data = await resp.json()
                # Response: JSON array, result at [0][0]
                translated_text = ""
                if isinstance(data, list) and len(data) > 0:
                    first = data[0]
                    if isinstance(first, list) and len(first) > 0:
                        translated_text = str(first[0]) if first[0] else ""

                if stream:
                    for chunk_text in split_text_chunks(translated_text):
                        yield chunk_text
                else:
                    yield translated_text

        except PlatformError:
            raise
        except Exception as e:
            self._last_error_time = time.time()
            raise PlatformError(
                "googletranslate 请求失败: {}".format(e)
            ) from e

    async def close(self) -> None:
        """清理资源。"""
        return
