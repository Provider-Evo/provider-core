"""DeepL 翻译 HTTP 客户端。

负责 API Key 管理、候选项构造与翻译请求。
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
from ..accounts import API_KEYS
from .constants import (
    CAPS,
    DEFAULT_SOURCE_LANG,
    DEFAULT_TARGET_LANG,
    FREE_BASE_URL,
    PAID_BASE_URL,
    RATE_LIMIT_COOLDOWN,
    RECOVERY_INTERVAL,
    TRANSLATE_PATH,
)

logger = logging.getLogger(__name__)
MAX_RETRIES: int = 3


class _KeyState:
    """单个 API Key 的运行时状态。"""

    __slots__ = (
        "key",
        "valid",
        "busy",
        "error_count",
        "consecutive_failures",
        "last_error_time",
        "rate_limit_until",
        "is_free",
        "base_url",
    )

    def __init__(self, key: str) -> None:
        """初始化 Key 状态。"""
        self.key: str = key
        self.valid: bool = True
        self.busy: bool = False
        self.error_count: int = 0
        self.consecutive_failures: int = 0
        self.last_error_time: float = 0.0
        self.rate_limit_until: float = 0.0
        # DeepL 免费 Key 以 ":fx" 结尾
        self.is_free: bool = key.strip().endswith(":fx")
        self.base_url: str = FREE_BASE_URL if self.is_free else PAID_BASE_URL

    @property
    def available(self) -> bool:
        """判断是否可用。"""
        if not self.valid:
            if time.time() - self.last_error_time >= RECOVERY_INTERVAL:
                self.valid = True
                self.error_count = 0
                self.consecutive_failures = 0
            else:
                return False
        if self.busy:
            return False
        if self.rate_limit_until > time.time():
            return False
        if self.consecutive_failures >= 3:
            if time.time() - self.last_error_time < RATE_LIMIT_COOLDOWN:
                return False
            self.consecutive_failures = 0
        return True

    def mark_success(self) -> None:
        """标记请求成功。"""
        self.busy = False
        self.consecutive_failures = 0

    def mark_failure(self, status: int = 0, message: str = "") -> None:
        """根据 HTTP 状态码分类处理失败。

        Args:
            status: HTTP 状态码。
            message: 上游返回的错误信息。
        """
        self.busy = False
        self.last_error_time = time.time()
        if status in (401, 403) or "auth" in message.lower():
            self.valid = False
            logger.warning(
                "deepl Key 无效 (HTTP%d): %s... | %s",
                status,
                self.key[:12],
                message[:100],
            )
        elif status == 429 or "quota" in message.lower():
            self.rate_limit_until = time.time() + RATE_LIMIT_COOLDOWN
            logger.warning("deepl Key 限速/配额耗尽: %s...", self.key[:12])
        elif status in (500, 502, 503, 504):
            self.consecutive_failures += 1
            self.error_count += 1
        else:
            self.consecutive_failures += 1
            self.error_count += 1


class DeepLClient:
    """DeepL 翻译 HTTP 客户端。"""

    def __init__(self) -> None:
        """初始化客户端。"""
        self._session: Optional[aiohttp.ClientSession] = None
        self._keys: List[_KeyState] = []

    async def init_immediate(self, session: aiohttp.ClientSession) -> None:
        """立即初始化。

        Args:
            session: 共享 aiohttp 会话。
        """
        self._session = session
        self._keys = [_KeyState(k) for k in API_KEYS if k and k.strip()]
        logger.debug(
            "deepl 客户端初始化完成, %d 个 APIKey",
            len(self._keys),
        )

    def _find_key(self, candidate: Candidate) -> Optional[_KeyState]:
        """根据候选项找到对应的 KeyState。"""
        api_key = candidate.meta.get("api_key", "")
        for ks in self._keys:
            if ks.key == api_key:
                return ks
        return None

    async def candidates(self) -> List[Candidate]:
        """每个可用 Key 生成一个候选项。"""
        from .constants import MODELS
        models = list(MODELS)
        return [
            Candidate(
                id=make_id("deepl", ks.key[:12]),
                platform="deepl",
                resource_id=ks.key[:12],
                models=list(models),
                context_length=None,
                meta={"api_key": ks.key},
                **CAPS,
            )
            for ks in self._keys
            if ks.available
        ]

    async def ensure_candidates(self, count: int) -> int:
        """返回可用 Key 数量。"""
        return sum(1 for ks in self._keys if ks.available)

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
            model: 模型名（忽略，翻译平台统一处理）。
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
                    candidate, text, source_lang, target_lang, stream,
                ):
                    yield chunk
                return
            except PlatformError as e:
                msg = str(e).lower()
                if "auth" in msg or "quota" in msg:
                    raise
                last_exc = e
                logger.warning(
                    "deepl 重试 %d/%d: %s",
                    attempt + 1,
                    MAX_RETRIES,
                    e,
                )
            except Exception as e:
                last_exc = e
                logger.warning(
                    "deepl 重试 %d/%d: %s",
                    attempt + 1,
                    MAX_RETRIES,
                    e,
                )
        if last_exc:
            raise last_exc

    async def _do_request(
        self,
        candidate: Candidate,
        text: str,
        source_lang: str,
        target_lang: str,
        stream: bool,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """执行单次 DeepL 翻译请求。

        Args:
            candidate: 候选项。
            text: 待翻译文本。
            source_lang: 源语言代码。
            target_lang: 目标语言代码。
            stream: 是否流式返回。
        """
        ks = self._find_key(candidate)
        if not ks:
            raise PlatformError("deepl: 未找到对应 APIKey")

        url = "{}{}".format(ks.base_url, TRANSLATE_PATH)
        headers = {
            "DeepL-Auth-Key": ks.key,
            "Content-Type": "application/x-www-form-urlencoded",
        }

        # URL-encoded form data
        form_data = {
            "text": text,
            "target_lang": target_lang.upper(),
        }
        if source_lang:
            form_data["source_lang"] = source_lang.upper()

        ks.busy = True
        try:
            async with self._session.post(
                url,
                headers=headers,
                data=form_data,
                ssl=False,
                timeout=aiohttp.ClientTimeout(connect=10, total=60),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    ks.mark_failure(resp.status, body)
                    raise PlatformError(
                        "deepl HTTP{}: {}".format(resp.status, body[:200])
                    )

                data = await resp.json()
                ks.mark_success()

                translations = data.get("translations", [])
                if not translations:
                    yield ""
                    return

                translated_text = translations[0].get("text", "")

                if stream:
                    # 按句子分割，模拟流式输出
                    for chunk_text in split_text_chunks(translated_text):
                        yield chunk_text
                else:
                    yield translated_text

        except PlatformError:
            raise
        except Exception as e:
            ks.mark_failure(0, str(e))
            raise PlatformError(
                "deepl 请求失败: {}".format(e)
            ) from e

    async def close(self) -> None:
        """清理资源。"""
        return
