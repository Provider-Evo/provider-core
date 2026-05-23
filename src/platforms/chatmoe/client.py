"""ChatMoe HTTP 客户端"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp

from src.core.candidate import Candidate, make_id
from src.platforms.chatmoe.accounts import API_KEYS
from src.platforms.chatmoe.util import (
    BASE_URL,
    CHAT_PATH,
    build_headers,
    build_payload,
    parse_sse_line,
)

logger = logging.getLogger(__name__)
MAX_RETRIES: int = 3


class ChatmoeClient:
    """ChatMoe HTTP 客户端。"""

    def __init__(self) -> None:
        self._session: Any = None
        self._models: List[str] = []
        self._candidates: List[Candidate] = []

    async def init_immediate(self, session: aiohttp.ClientSession) -> None:
        """立即初始化，不阻塞。

        Args:
            session: 共享的 aiohttp ClientSession。
        """
        self._session = session
        self._rebuild_candidates()
        logger.info("chatmoe 客户端初始化完成，候选项: %d 个", len(self._candidates))

    async def background_setup(self) -> None:
        """后台完善。

        ChatMoe 使用内置静态 Key，无需登录或 token 刷新，此方法为空。
        """
        return

    def update_models(self, models: List[str]) -> None:
        """更新模型列表，同步刷新所有候选项的 models 字段。

        Args:
            models: 新的模型列表。
        """
        self._models = list(models)
        for cand in self._candidates:
            cand.models = list(models)

    def _rebuild_candidates(self) -> None:
        """根据当前凭证重建候选项列表。"""
        from src.platforms.chatmoe.adapter import CAPS

        self._candidates = [
            Candidate(
                id=make_id("chatmoe"),
                platform="chatmoe",
                resource_id=key[:12],
                models=list(self._models),
                context_length=None,
                meta={"api_key": key},
                **CAPS,
            )
            for key in API_KEYS
            if key
        ]

    async def candidates(self) -> List[Candidate]:
        """返回当前候选项列表。

        Returns:
            候选项列表的副本。
        """
        return list(self._candidates)

    async def ensure_candidates(self, count: int) -> int:
        """返回可用候选项数量。

        Args:
            count: 期望数量（本实现不扩容）。

        Returns:
            当前实际候选项数量。
        """
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
        """执行聊天补全，含指数退避重试。

        Args:
            candidate: 选中的候选项。
            messages: 消息列表。
            model: 模型名称。
            stream: 是否流式输出。
            thinking: 是否启用深度思考。
            search: 是否启用联网搜索。
            **kw: 其他扩展参数。

        Yields:
            文本片段或结构化数据字典。

        Raises:
            Exception: 超过最大重试次数后抛出最后一次异常。
        """
        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                await asyncio.sleep(1.0 * (2 ** (attempt - 1)))
            try:
                async for chunk in self._do_request(
                    candidate, messages, model, stream,
                    thinking=thinking, search=search,
                ):
                    yield chunk
                return
            except Exception as e:
                last_exc = e
                logger.warning(
                    "chatmoe 重试 %d/%d: %s", attempt + 1, MAX_RETRIES, e
                )
        if last_exc is not None:
            raise last_exc

    async def _do_request(
        self,
        candidate: Candidate,
        messages: List[Dict[str, Any]],
        model: str,
        stream: bool,
        *,
        thinking: bool = False,
        search: bool = False,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """执行单次 HTTP 请求。

        Args:
            candidate: 选中的候选项，用于提取凭证。
            messages: 消息列表。
            model: 模型名称。
            stream: 是否流式输出。
            thinking: 是否启用深度思考。
            search: 是否启用联网搜索。

        Yields:
            文本片段或结构化数据字典。

        Raises:
            Exception: HTTP 状态码非 200 时抛出。
        """
        token: str = candidate.meta.get("api_key", "")
        headers = build_headers(token)
        payload = build_payload(
            messages, model,
            stream=stream,
            thinking=thinking,
            search=search,
        )
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
                raise Exception(
                    "chatmoe HTTP {}: {}".format(resp.status, body)
                )

            if stream:
                thinking_started = False
                thinking_ended = False

                async for line in resp.content:
                    if not line:
                        continue
                    text = line.decode("utf-8", errors="replace").strip()
                    if not text or not text.startswith("data:"):
                        continue
                    data_str = text[5:].strip()
                    if data_str == "[DONE]":
                        break

                    data = parse_sse_line(data_str)
                    if data is None or not isinstance(data, dict):
                        continue

                    choices = data.get("choices", [])
                    if not choices:
                        # 检查顶层 usage
                        if data.get("usage"):
                            yield {"usage": data["usage"]}
                        continue

                    delta = choices[0].get("delta", {})
                    reasoning_content: Optional[str] = delta.get("reasoning_content")
                    content: Optional[str] = delta.get("content")

                    if thinking and reasoning_content:
                        if not thinking_started:
                            yield {"thinking": "<think>"}
                            thinking_started = True
                        yield {"thinking": reasoning_content}

                    if content:
                        if thinking and thinking_started and not thinking_ended:
                            yield {"thinking": "</think>\n\n"}
                            thinking_ended = True
                        yield content

                    if data.get("usage"):
                        yield {"usage": data["usage"]}
            else:
                obj = await resp.json()
                content_val: str = obj["choices"][0]["message"]["content"]
                yield content_val
                if obj.get("usage"):
                    yield {"usage": obj["usage"]}

    async def close(self) -> None:
        """清理资源（session 由外部管理，此处不关闭）。"""
        return
