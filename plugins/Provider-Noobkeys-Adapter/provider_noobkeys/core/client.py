"""NoobKeys HTTP 客户端（OpenAI 兼容协议，纯文本对话）。"""

from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp

from src.core.dispatch.candidate import Candidate, make_id
from src.core.errors import PlatformError
from src.logger import get_logger
from ..accounts import API_KEYS
from .constants import (
    BASE_URL,
    CAPS,
    CHAT_PATH,
    MODELS_PATH,
    RATE_LIMIT_COOLDOWN,
    RECOVERY_INTERVAL,
)
from .headers import build_headers
from .payloads import build_payload
from .sse import parse_sse_line

logger = get_logger(__name__)
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
        """根据 HTTP 状态码与上游错误信息分类处理失败。

        Args:
            status: HTTP 状态码。
            message: 上游返回的 ``error.message`` 原文（用于识别余额不足等）。
        """
        self.busy = False
        self.last_error_time = time.time()
        if status in (401, 403) or "authentication" in message.lower():
            self.valid = False
            logger.warning(
                "noobkeys Key 无效 (HTTP%d): %s... | %s",
                status,
                self.key[:12],
                message[:100],
            )
        elif status == 402 or "insufficient" in message.lower():
            self.valid = False
            logger.warning(
                "noobkeys Key 余额不足 (HTTP%d): %s...",
                status,
                self.key[:12],
            )
        elif status == 429:
            self.rate_limit_until = time.time() + RATE_LIMIT_COOLDOWN
            logger.warning("noobkeys Key 限速: %s...", self.key[:12])
        elif status in (500, 502, 503, 504):
            self.consecutive_failures += 1
            self.error_count += 1
        elif status in (400, 404, 422):
            logger.debug(
                "noobkeys 请求参数或模型错误 (HTTP%d): %s",
                status,
                message[:120],
            )
        else:
            self.consecutive_failures += 1
            self.error_count += 1


class NoobKeysClient:
    """NoobKeys HTTP 客户端。"""

    def __init__(self) -> None:
        """初始化客户端。"""
        self._session: Optional[aiohttp.ClientSession] = None
        self._models: List[str] = []
        self._keys: List[_KeyState] = []

    async def init_immediate(self, session: aiohttp.ClientSession) -> None:
        """立即初始化，不阻塞。

        Args:
            session: 共享 aiohttp 会话。
        """
        self._session = session
        self._keys = [_KeyState(k) for k in API_KEYS if k and k.strip()]
        logger.debug(
            "noobkeys 客户端初始化完成, %d 个 APIKey",
            len(self._keys),
        )

    async def background_setup(self) -> None:
        """后台完善：尝试拉取远程模型列表。"""
        try:
            models = await self.fetch_remote_models()
            if models:
                self.update_models(models)
        except Exception as e:
            logger.warning("noobkeys 后台拉取模型失败: %s", e)

    async def fetch_remote_models(self) -> List[str]:
        """从 NoobKeys 拉取可用模型列表。

        Returns:
            模型 ID 列表，失败时返回空列表。
        """
        if not self._session or not self._keys:
            return []

        ks = next((k for k in self._keys if k.available), None)
        if ks is None:
            return []

        headers = build_headers(ks.key)
        url = "{}{}".format(BASE_URL, MODELS_PATH)

        try:
            async with self._session.get(
                url,
                headers=headers,
                ssl=False,
                timeout=aiohttp.ClientTimeout(connect=10, total=30),
            ) as resp:
                if resp.status != 200:
                    logger.warning(
                        "noobkeys 拉取模型列表失败, HTTP%d",
                        resp.status,
                    )
                    return []
                data = await resp.json()
                model_data = data.get("data", [])
                if isinstance(model_data, list):
                    return [
                        m.get("id", "")
                        for m in model_data
                        if isinstance(m, dict) and m.get("id")
                    ]
                return []
        except Exception as e:
            logger.warning("noobkeys 拉取模型列表异常: %s", e)
            return []

    def update_models(self, models: List[str]) -> None:
        """更新模型列表。

        Args:
            models: 新的模型列表。
        """
        self._models = list(models)

    def _find_key(self, candidate: Candidate) -> Optional[_KeyState]:
        """根据候选项找到对应的 KeyState。"""
        api_key = candidate.meta.get("api_key", "")
        for ks in self._keys:
            if ks.key == api_key:
                return ks
        return None

    async def candidates(self) -> List[Candidate]:
        """每个可用 Key 生成一个候选项。"""
        models = self._models
        return [
            Candidate(
                id=make_id("noobkeys", ks.key[:12]),
                platform="noobkeys",
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
        """执行聊天补全，含指数退避重试。

        Args:
            candidate: 候选项。
            messages: 消息列表。
            model: 模型名。
            stream: 是否流式。
            **kw: 转发给 ``build_payload`` 的额外参数；
                ``thinking`` / ``search`` 等不支持字段会被静默丢弃。
        """
        payload_kw: Dict[str, Any] = {
            k: v
            for k, v in kw.items()
            if k not in ("thinking", "search")
        }
        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                await asyncio.sleep(1.0 * (2 ** (attempt - 1)))
            try:
                async for chunk in self._do_request(
                    candidate,
                    messages,
                    model,
                    stream,
                    **payload_kw,
                ):
                    yield chunk
                return
            except PlatformError as e:
                msg = str(e).lower()
                if (
                    "balance" in msg
                    or "insufficient" in msg
                    or "authentication" in msg
                ):
                    raise
                last_exc = e
                logger.warning(
                    "noobkeys 重试 %d/%d: %s",
                    attempt + 1,
                    MAX_RETRIES,
                    e,
                )
            except Exception as e:
                last_exc = e
                logger.warning(
                    "noobkeys 重试 %d/%d: %s",
                    attempt + 1,
                    MAX_RETRIES,
                    e,
                )
        if last_exc:
            raise last_exc

    async def _do_request(
        self,
        candidate: Candidate,
        messages: List[Dict[str, Any]],
        model: str,
        stream: bool,
        **kw: Any,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """执行单次 HTTP 请求。"""
        ks = self._find_key(candidate)
        if not ks:
            raise PlatformError("noobkeys: 未找到对应 APIKey")

        headers = build_headers(ks.key)
        payload = build_payload(messages, model, stream=stream, **kw)
        url = "{}{}".format(BASE_URL, CHAT_PATH)

        ks.busy = True
        try:
            async with self._session.post(
                url,
                headers=headers,
                json=payload,
                ssl=False,
                timeout=aiohttp.ClientTimeout(
                    connect=10,
                    total=600 if stream else 120,
                ),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    error_msg = _extract_error_message(body)
                    ks.mark_failure(resp.status, error_msg)
                    raise PlatformError(
                        "noobkeys HTTP{}: {}".format(
                            resp.status,
                            body[:200],
                        )
                    )

                if not stream:
                    data = await resp.json()
                    ks.mark_success()
                    for item in _iter_non_stream_items(data):
                        yield item
                else:
                    async for item in self._iter_stream(resp, ks):
                        yield item
        except PlatformError:
            raise
        except Exception as e:
            ks.mark_failure(0, str(e))
            raise PlatformError(
                "noobkeys 请求失败: {}".format(e)
            ) from e

    async def _iter_stream(
        self,
        resp: aiohttp.ClientResponse,
        ks: _KeyState,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """逐行解析 SSE 流并产出增量。"""
        async for raw in resp.content:
            text = raw.decode("utf-8", errors="replace").strip()
            if not text or not text.startswith("data:"):
                continue
            data_str = text[5:].strip()
            if data_str == "[DONE]":
                break
            parsed = parse_sse_line(data_str)
            if parsed is not None:
                yield parsed
        ks.mark_success()

    async def close(self) -> None:
        """清理资源。"""
        return


def _extract_error_message(body: str) -> str:
    """从响应体中提取 ``error.message``，便于按业务分类错误。

    Args:
        body: HTTP 响应体原文。

    Returns:
        错误消息字符串；无法解析时返回空字符串。
    """
    if not body:
        return ""
    try:
        import json as _json

        obj = _json.loads(body)
        err = obj.get("error") if isinstance(obj, dict) else None
        if isinstance(err, dict):
            return str(err.get("message", ""))
        if isinstance(err, str):
            return err
    except (ValueError, AttributeError):
        return ""
    return ""


def _iter_non_stream_items(
    data: Dict[str, Any],
) -> Any:
    """从非流式响应 JSON 中依次产出 thinking / 文本 / usage。

    Args:
        data: 非流式响应 JSON。

    Yields:
        ``str``（文本片段）或 ``dict``（thinking / usage）。
    """
    choices = data.get("choices") or []
    if choices:
        msg = choices[0].get("message", {}) or {}
        reasoning = msg.get("reasoning_content") or msg.get("reasoning")
        if reasoning:
            yield {"thinking": reasoning}
        content = msg.get("content", "") or ""
        if content:
            yield content
    usage = data.get("usage")
    if usage and isinstance(usage, dict):
        yield {
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
            }
        }
