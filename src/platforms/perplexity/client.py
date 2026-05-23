from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp

from src.core.candidate import Candidate, make_id
from src.platforms.perplexity.util import (
    BASE_URL,
    CHAT_PATH,
    MODELS,
    MODEL_ALIASES,
    build_headers,
    build_payload,
    parse_sse_line,
)

logger = logging.getLogger(__name__)
MAX_RETRIES = 3


class PerplexityClient:
    def __init__(self) -> None:
        self._session: Optional[aiohttp.ClientSession] = None

    async def init(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        logger.info("perplexity 初始化完成")

    async def candidates(self) -> List[Candidate]:
        # 无需 API Key，使用公共通道（如需自定义可后续扩展）
        return [
            Candidate(
                id=make_id("perplexity"),
                platform="perplexity",
                resource_id="public",
                models=MODELS,
                meta={},
                chat=True,
                tools=False,
                vision=False,
                thinking=True,
                search=True,
            )
        ]

    async def ensure_candidates(self, count: int) -> int:
        return 1

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
                async for chunk in self._do_request(candidate, messages, model, stream):
                    yield chunk
                return
            except Exception as e:
                last_exc = e
                logger.warning("perplexity 重试 %d/%d: %s", attempt + 1, MAX_RETRIES, e)
        if last_exc is not None:
            raise last_exc

    async def _do_request(
        self,
        candidate: Candidate,
        messages: List[Dict[str, Any]],
        model: str,
        stream: bool,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        if self._session is None:
            raise RuntimeError("session not initialized")

        # 提取用户消息为 prompt
        prompt = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                content = m.get("content")
                if isinstance(content, list):
                    prompt = "\n".join([item.get("text", "") for item in content if isinstance(item, dict)])
                else:
                    prompt = str(content)
                break

        request_id = str(uuid.uuid4())
        referer = f"{BASE_URL}/"
        headers = build_headers("", referer=referer, request_id=request_id)

        # 简化会话信息：首次请求
        convo = {
            "frontend_uid": str(uuid.uuid4()),
            "frontend_context_uuid": str(uuid.uuid4()),
            "last_backend_uuid": None,
            "read_write_token": None,
            "thread_url_slug": None,
        }

        payload = build_payload(prompt, model, followup=False, convo=convo)
        url = f"{BASE_URL}{CHAT_PATH}"

        async with self._session.post(
            url,
            json=payload,
            headers=headers,
            ssl=False,
            timeout=aiohttp.ClientTimeout(connect=10, total=300),
        ) as resp:
            if resp.status != 200:
                raise Exception(f"perplexity HTTP {resp.status}: {await resp.text()}")

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

    async def close(self) -> None:
        return None
