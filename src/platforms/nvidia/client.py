# src/platforms/nvidia/client.py
"""Nvidia客户端"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp

from src.core.candidate import Candidate, make_id
from src.core.errors import PlatformError
from src.platforms.nvidia.accounts import API_KEYS
from src.platforms.nvidia.util import (
    BASE_URL,
    CHAT_PATH,
    MAX_TOKENS,
    RECOVERY_INTERVAL,
    build_headers,
    build_payload,
    parse_sse_line,
)

logger = logging.getLogger(__name__)
MAX_RETRIES: int = 3


class _KeyState:
    """单个APIKey的运行时状态"""

    __slots__ = (
        "key", "valid", "busy", "consecutive_failures", "last_error_time",
    )

    def __init__(self, key: str) -> None:
        """初始化Key状态。"""
        self.key: str = key
        self.valid: bool = True
        self.busy: bool = False
        self.consecutive_failures: int = 0
        self.last_error_time: float = 0.0

    @property
    def available(self) -> bool:
        """判断是否可用。"""
        if not self.valid:
            if time.time() - self.last_error_time >= RECOVERY_INTERVAL:
                self.valid = True
                self.consecutive_failures = 0
            else:
                return False
        if self.busy:
            return False
        if self.consecutive_failures >= 3:
            if time.time() - self.last_error_time < RECOVERY_INTERVAL:
                return False
            self.consecutive_failures = 0
        return True

    def mark_success(self) -> None:
        """标记请求成功。"""
        self.busy = False
        self.consecutive_failures = 0

    def mark_failure(self, status: int = 0) -> None:
        """根据HTTP状态码处理失败。"""
        self.busy = False
        self.last_error_time = time.time()
        if status in (401, 402, 403):
            self.valid = False
            logger.warning(
                "nvidia Key无效 (HTTP%d): %s...", status, self.key[:16]
            )
        else:
            self.consecutive_failures += 1


class NvidiaClient:
    """Nvidia HTTP客户端"""

    def __init__(self) -> None:
        self._session: Optional[aiohttp.ClientSession] = None
        self._models: List[str] = []
        self._keys: List[_KeyState] = []
        self._candidates: List[Candidate] = []

    async def init_immediate(self, session: aiohttp.ClientSession) -> None:
        """立即初始化，不阻塞。"""
        self._session = session
        self._keys = [_KeyState(k) for k in API_KEYS if k and k.strip()]
        self._rebuild_candidates()
        logger.info(
            "nvidia客户端初始化完成, %d个APIKey, %d个模型",
            len(self._keys),
            len(self._models),
        )

    async def background_setup(self) -> None:
        """后台完善（Nvidia无需登录）。"""
        return

    def update_models(self, models: List[str]) -> None:
        """更新模型列表，同步刷新所有候选项的models字段。

        Args:
            models: 新的模型列表。
        """
        self._models = list(models)
        for cand in self._candidates:
            cand.models = list(models)

    def _rebuild_candidates(self) -> None:
        """根据当前凭证重建候选项列表。"""
        from src.platforms.nvidia.adapter import CAPS

        self._candidates = [
            Candidate(
                id=make_id("nvidia"),
                platform="nvidia",
                resource_id=ks.key[:16],
                models=self._models,
                context_length=None,
                meta={"api_key": ks.key},
                **CAPS,
            )
            for ks in self._keys
            if ks.available
        ]

    def _find_key(self, candidate: Candidate) -> Optional[_KeyState]:
        """根据候选项找到对应的KeyState。"""
        api_key = candidate.meta.get("api_key", "")
        for ks in self._keys:
            if ks.key == api_key:
                return ks
        return None

    async def candidates(self) -> List[Candidate]:
        """返回当前候选项列表。"""
        from src.platforms.nvidia.adapter import CAPS

        return [
            Candidate(
                id=make_id("nvidia"),
                platform="nvidia",
                resource_id=ks.key[:16],
                models=list(self._models),
                context_length=None,
                meta={"api_key": ks.key},
                **CAPS,
            )
            for ks in self._keys
            if ks.available
        ]

    async def ensure_candidates(self, count: int) -> int:
        """返回可用候选项数量。"""
        return sum(1 for ks in self._keys if ks.available)

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
        """执行聊天补全，含重试。"""
        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                await asyncio.sleep(1.0 * (2 ** (attempt - 1)))
            try:
                async for chunk in self._do_request(
                    candidate, messages, model, stream, **kw
                ):
                    yield chunk
                return
            except PlatformError:
                raise
            except Exception as e:
                last_exc = e
                logger.warning(
                    "nvidia重试 %d/%d: %s", attempt + 1, MAX_RETRIES, e
                )
        if last_exc:
            raise last_exc

    async def _do_request(
        self,
        candidate: Candidate,
        messages: List[Dict],
        model: str,
        stream: bool,
        **kw: Any,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """执行单次HTTP请求。"""
        ks = self._find_key(candidate)
        if not ks:
            raise PlatformError("nvidia: 未找到对应APIKey")

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
                    ks.mark_failure(resp.status)
                    raise PlatformError(
                        "nvidia HTTP{}: {}".format(resp.status, body[:300])
                    )

                if not stream:
                    data = await resp.json()
                    ks.mark_success()
                    choice = (data.get("choices") or [{}])[0]
                    content = choice.get("message", {}).get("content", "")
                    if content:
                        yield content
                    usage = data.get("usage")
                    if usage:
                        yield {"usage": {
                            "prompt_tokens": usage.get("prompt_tokens", 0),
                            "completion_tokens": usage.get("completion_tokens", 0),
                        }}
                else:
                    async for line in resp.content:
                        text = line.decode("utf-8", errors="replace").strip()
                        if not text or not text.startswith("data:"):
                            continue
                        data_str = text[5:].strip()
                        if data_str == "[DONE]":
                            break
                        parsed = parse_sse_line(data_str)
                        if parsed is not None:
                            yield parsed
                    ks.mark_success()
        except PlatformError:
            raise
        except Exception as e:
            ks.mark_failure(0)
            raise PlatformError("nvidia请求失败: {}".format(e)) from e

    async def close(self) -> None:
        """清理资源。"""
        return
