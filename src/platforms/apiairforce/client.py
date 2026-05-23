from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp

from src.core.candidate import Candidate, make_id
from src.platforms.apiairforce.accounts import API_KEYS
from src.platforms.apiairforce.util import (
    BASE_URL,
    CHAT_PATH,
    MODELS_PATH,
    build_headers,
    build_payload,
    parse_sse_line,
)

logger = logging.getLogger(__name__)
MAX_RETRIES: int = 3
MODEL_CACHE_TTL: int = 24 * 60 * 60  # 24 小时


class ApiairforceClient:
    """apiairforce HTTP 客户端。"""

    def __init__(self) -> None:
        self._session: Optional[aiohttp.ClientSession] = None
        self._models_cache: List[str] = []
        self._models_ts: float = 0.0

    async def init(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        logger.info("apiairforce 初始化完成")

    async def fetch_remote_models(self) -> List[str]:
        """拉取远程模型列表，24 小时缓存。"""
        now = time.time()
        if self._models_cache and now - self._models_ts < MODEL_CACHE_TTL:
            return self._models_cache
        if self._session is None:
            return self._models_cache
        url = f"{BASE_URL}{MODELS_PATH}"
        try:
            async with self._session.get(url, headers=build_headers(), ssl=False, timeout=30) as resp:
                if resp.status != 200:
                    logger.warning("apiairforce 拉取模型失败 HTTP %s", resp.status)
                    return self._models_cache
                data = await resp.json()
                items = data.get("data") or []
                models = [m.get("id") for m in items if m.get("id")]
                if models:
                    self._models_cache = models
                    self._models_ts = now
        except Exception as e:
            logger.warning("apiairforce 拉取模型异常: %s", e)
        return self._models_cache

    async def candidates(self) -> List[Candidate]:
        models = await self.fetch_remote_models()
        return [
            Candidate(
                id=make_id("apiairforce"),
                platform="apiairforce",
                resource_id=(key or "public")[:12],
                models=models if models else ["roleplay:free"],
                meta={"api_key": key},
                chat=True,
                tools=False,
                vision=False,
                thinking=False,
                search=False,
                image_gen=False,
            )
            for key in API_KEYS
        ]

    async def ensure_candidates(self, count: int) -> int:
        return len(API_KEYS)

    async def complete(
        self,
        candidate: Candidate,
        messages: List[Dict[str, Any]],
        model: str,
        stream: bool,
        *,
        thinking: bool = False,
        search: bool = False,
        **kw: Any,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
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
            except Exception as e:
                last_exc = e
                logger.warning("apiairforce 重试 %d/%d: %s", attempt + 1, MAX_RETRIES, e)
        if last_exc is not None:
            raise last_exc

    async def _do_request(
        self,
        candidate: Candidate,
        messages: List[Dict[str, Any]],
        model: str,
        stream: bool,
        **kw: Any,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        if self._session is None:
            raise RuntimeError("session not initialized")
        headers = build_headers(candidate.meta.get("api_key", ""))
        payload = build_payload(messages, model, stream=stream, **kw)
        url = f"{BASE_URL}{CHAT_PATH}"
        async with self._session.post(
            url,
            json=payload,
            headers=headers,
            ssl=False,
            timeout=aiohttp.ClientTimeout(connect=10, total=300),
        ) as resp:
            if resp.status != 200:
                raise Exception(f"apiairforce HTTP {resp.status}: {await resp.text()}")
            if stream:
                async for line in resp.content:
                    if not line:
                        continue
                    text = line.decode("utf-8", errors="replace").strip()
                    if not text or not text.startswith("data:"):
                        continue
                    data_str = text[5:].strip()
                    if data_str == "[DONE]":
                        break
                    parsed = parse_sse_line(data_str)
                    if parsed is not None:
                        yield parsed
            else:
                obj = await resp.json()
                choices = obj.get("choices") or []
                if choices:
                    content = choices[0].get("message", {}).get("content")
                    if content:
                        yield content
                if obj.get("usage"):
                    yield {"usage": obj["usage"]}

    async def close(self) -> None:
        return None
