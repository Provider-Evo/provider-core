"""Azure Translator HTTP 客户端。

负责账号管理、候选项构造与翻译请求。
使用 Azure Cognitive Services Translator API v3.0。
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp

from echotools.translate import extract_text_from_messages, split_text_chunks

from src.core.dispatch.candidate import Candidate, make_id
from src.core.errors import PlatformError
from src.logger import get_logger
from ..accounts import ACCOUNTS, Account
from .constants import (
    API_VERSION,
    BASE_URL,
    CAPS,
    DEFAULT_SOURCE_LANG,
    DEFAULT_TARGET_LANG,
    MODELS,
    RATE_LIMIT_COOLDOWN,
    RECOVERY_INTERVAL,
    TRANSLATE_PATH,
)

logger = get_logger(__name__)
MAX_RETRIES: int = 3


class _AccountState:
    """单个 Azure 账号的运行时状态。"""

    __slots__ = (
        "account",
        "valid",
        "busy",
        "error_count",
        "consecutive_failures",
        "last_error_time",
        "rate_limit_until",
    )

    def __init__(self, account: Account) -> None:
        """初始化账号状态。"""
        self.account: Account = account
        self.valid: bool = True
        self.busy: bool = False
        self.error_count: int = 0
        self.consecutive_failures: int = 0
        self.last_error_time: float = 0.0
        self.rate_limit_until: float = 0.0

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
        if status in (401, 403) or "access denied" in message.lower():
            self.valid = False
            logger.warning(
                "azuretranslate Key 无效 (HTTP%d): %s... | %s",
                status,
                self.account.api_key[:12],
                message[:100],
            )
        elif status == 429:
            self.rate_limit_until = time.time() + RATE_LIMIT_COOLDOWN
            logger.warning(
                "azuretranslate Key 限速: %s...",
                self.account.api_key[:12],
            )
        elif status in (500, 502, 503, 504):
            self.consecutive_failures += 1
            self.error_count += 1
        else:
            self.consecutive_failures += 1
            self.error_count += 1


class AzureTranslateClient:
    """Azure Translator HTTP 客户端。"""

    def __init__(self) -> None:
        """初始化客户端。"""
        self._session: Optional[aiohttp.ClientSession] = None
        self._accounts: List[_AccountState] = []

    async def init_immediate(self, session: aiohttp.ClientSession) -> None:
        """立即初始化。

        Args:
            session: 共享 aiohttp 会话。
        """
        self._session = session
        self._accounts = [
            _AccountState(a) for a in ACCOUNTS
            if a.api_key and a.api_key.strip()
        ]
        logger.debug(
            "azuretranslate 客户端初始化完成, %d 个账号",
            len(self._accounts),
        )

    def _find_account(self, candidate: Candidate) -> Optional[_AccountState]:
        """根据候选项找到对应的 AccountState。"""
        api_key = candidate.meta.get("api_key", "")
        for acc_state in self._accounts:
            if acc_state.account.api_key == api_key:
                return acc_state
        return None

    async def candidates(self) -> List[Candidate]:
        """每个可用账号生成一个候选项。"""
        models = list(MODELS)
        return [
            Candidate(
                id=make_id(
                    "azuretranslate",
                    acc_state.account.api_key[:12],
                ),
                platform="azuretranslate",
                resource_id=acc_state.account.api_key[:12],
                models=list(models),
                context_length=None,
                meta={
                    "api_key": acc_state.account.api_key,
                    "region": acc_state.account.region,
                },
                **CAPS,
            )
            for acc_state in self._accounts
            if acc_state.available
        ]

    async def ensure_candidates(self, count: int) -> int:
        """返回可用账号数量。"""
        return sum(1 for a in self._accounts if a.available)

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
                    candidate, text, source_lang, target_lang, stream,
                ):
                    yield chunk
                return
            except PlatformError as e:
                msg = str(e).lower()
                if "access denied" in msg or "auth" in msg:
                    raise
                last_exc = e
                logger.warning(
                    "azuretranslate 重试 %d/%d: %s",
                    attempt + 1,
                    MAX_RETRIES,
                    e,
                )
            except Exception as e:
                last_exc = e
                logger.warning(
                    "azuretranslate 重试 %d/%d: %s",
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
        """执行单次 Azure Translator 请求。

        Args:
            candidate: 候选项。
            text: 待翻译文本。
            source_lang: 源语言代码。
            target_lang: 目标语言代码。
            stream: 是否流式返回。
        """
        acc_state = self._find_account(candidate)
        if not acc_state:
            raise PlatformError("azuretranslate: 未找到对应账号")

        account = acc_state.account

        # Build URL with query params
        url = "{}{}".format(BASE_URL, TRANSLATE_PATH)
        params = {
            "api-version": API_VERSION,
            "to": target_lang,
        }
        if source_lang:
            params["from"] = source_lang

        headers = {
            "Ocp-Apim-Subscription-Key": account.api_key,
            "Content-Type": "application/json",
        }
        # Region header (required for multi-service resources)
        if account.region and account.region != "global":
            headers["Ocp-Apim-Subscription-Region"] = account.region

        # Azure Translator body: [{"Text": "..."}]
        body = [{"Text": text}]

        acc_state.busy = True
        try:
            async with self._session.post(
                url,
                headers=headers,
                params=params,
                json=body,
                ssl=False,
                timeout=aiohttp.ClientTimeout(connect=10, total=60),
            ) as resp:
                if resp.status != 200:
                    body_text = await resp.text()
                    acc_state.mark_failure(resp.status, body_text)
                    raise PlatformError(
                        "azuretranslate HTTP{}: {}".format(
                            resp.status, body_text[:200]
                        )
                    )

                data = await resp.json()
                acc_state.mark_success()

                # Response: [{"translations": [{"text": "..."}]}]
                translated_text = ""
                if isinstance(data, list) and len(data) > 0:
                    first = data[0]
                    if isinstance(first, dict):
                        translations = first.get("translations", [])
                        if translations and isinstance(translations, list):
                            translated_text = translations[0].get("text", "")

                if stream:
                    for chunk_text in split_text_chunks(translated_text):
                        yield chunk_text
                else:
                    yield translated_text

        except PlatformError:
            raise
        except Exception as e:
            acc_state.mark_failure(0, str(e))
            raise PlatformError(
                "azuretranslate 请求失败: {}".format(e)
            ) from e

    async def close(self) -> None:
        """清理资源。"""
        return
