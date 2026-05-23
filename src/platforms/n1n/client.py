# src/platforms/n1n/client.py
"""N1N客户端"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp

from src.core.candidate import Candidate, make_id
from src.platforms.n1n.accounts import API_KEYS
from src.platforms.n1n.util import (
    BASE_URL,
    CHAT_PATH,
    MODELS_PATH,
    build_headers,
    build_payload,
    parse_sse_line,
)

logger = logging.getLogger(__name__)
MAX_RETRIES: int = 3


class N1nClient:
    """N1N HTTP客户端"""

    def __init__(self) -> None:
        self._session: Optional[aiohttp.ClientSession] = None
        self._models: List[str] = []
        self._candidates: List[Candidate] = []

    async def init_immediate(self, session: aiohttp.ClientSession) -> None:
        """立即初始化，不阻塞。"""
        self._session = session
        self._rebuild_candidates()
        logger.info("n1n客户端初始化完成")

    async def background_setup(self) -> None:
        """后台完善：拉取远程模型列表。"""
        try:
            models = await self.fetch_remote_models()
            if models:
                self.update_models(models)
        except Exception as e:
            logger.warning("n1n后台拉取模型失败: %s", e)

    async def fetch_remote_models(self) -> List[str]:
        """从远程接口拉取模型列表。

        Returns:
            模型ID列表，失败时返回空列表。
        """
        if not self._session:
            return []

        url = "{}{}".format(BASE_URL, MODELS_PATH)
        headers = build_headers()

        try:
            async with self._session.get(
                url,
                headers=headers,
                ssl=False,
                timeout=aiohttp.ClientTimeout(connect=10, total=30),
            ) as resp:
                if resp.status != 200:
                    logger.warning("n1n拉取模型列表失败, HTTP%d", resp.status)
                    return []
                data = await resp.json()
                if not data.get("success"):
                    logger.warning("n1n模型列表接口返回失败: %s", data.get("message"))
                    return []
                remote_models = data.get("data", [])
                if isinstance(remote_models, list) and remote_models:
                    logger.info("n1n: 远程接口返回%d个模型", len(remote_models))
                    return [m for m in remote_models if isinstance(m, str)]
                logger.warning("n1n: 远程接口返回空模型列表")
                return []
        except Exception as e:
            logger.warning("n1n拉取远程模型列表异常: %s", e)
            return []

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
        from src.platforms.n1n.adapter import CAPS

        self._candidates = [
            Candidate(
                id=make_id("n1n"),
                platform="n1n",
                resource_id=key[:12],
                models=self._models,
                context_length=None,
                meta={"api_key": key},
                **CAPS,
            )
            for key in API_KEYS
            if key
        ]

    async def candidates(self) -> List[Candidate]:
        """返回当前候选项列表。"""
        return list(self._candidates)

    async def ensure_candidates(self, count: int) -> int:
        """返回可用候选项数量。"""
        return len(self._candidates)

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
        """执行聊天补全，含重试。"""
        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                await asyncio.sleep(1.0 * (2 ** (attempt - 1)))
            try:
                if stream:
                    async for chunk in self._do_stream_request(
                        candidate, messages, model
                    ):
                        yield chunk
                else:
                    async for chunk in self._do_request(
                        candidate, messages, model
                    ):
                        yield chunk
                return
            except Exception as e:
                last_exc = e
                logger.warning("n1n重试 %d/%d: %s", attempt + 1, MAX_RETRIES, e)
        if last_exc:
            raise last_exc

    async def _do_stream_request(
        self,
        candidate: Candidate,
        messages: List[Dict[str, Any]],
        model: str,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """执行单次流式HTTP请求。"""
        token = candidate.meta.get("api_key", "")
        headers = build_headers(token)
        payload = build_payload(messages, model, stream=True)
        url = "{}{}".format(BASE_URL, CHAT_PATH)

        async with self._session.post(
            url,
            json=payload,
            headers=headers,
            ssl=False,
            timeout=aiohttp.ClientTimeout(connect=10, total=300),
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise Exception("n1n HTTP{}: {}".format(resp.status, body[:500]))
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

    async def _do_request(
        self,
        candidate: Candidate,
        messages: List[Dict[str, Any]],
        model: str,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """执行单次非流式HTTP请求。"""
        token = candidate.meta.get("api_key", "")
        headers = build_headers(token)
        payload = build_payload(messages, model, stream=False)
        url = "{}{}".format(BASE_URL, CHAT_PATH)

        async with self._session.post(
            url,
            json=payload,
            headers=headers,
            ssl=False,
            timeout=aiohttp.ClientTimeout(connect=10, total=120),
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise Exception("n1n HTTP{}: {}".format(resp.status, body[:500]))
            obj = await resp.json()

            if "error" in obj:
                raise Exception("n1n API错误: {}".format(obj["error"]))

            choices = obj.get("choices", [])
            if choices:
                message = choices[0].get("message", {})
                content = message.get("content", "")
                if content:
                    yield content

            usage = obj.get("usage")
            if usage:
                yield {"usage": usage}

    async def close(self) -> None:
        """清理资源。"""
        return
