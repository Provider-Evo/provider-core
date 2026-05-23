"""CodeBuddy 客户端"""

from __future__ import annotations

import asyncio
import logging
import secrets
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp

from src.core.candidate import Candidate, make_id
from src.platforms.codebuddy.accounts import ACCOUNTS, Account
from src.platforms.codebuddy.util import (
    BASE_URL,
    CHAT_PATH,
    build_headers,
    build_payload,
    parse_sse_line,
)

logger = logging.getLogger(__name__)
MAX_RETRIES: int = 3


class CodebuddyClient:
    """CodeBuddy HTTP 客户端。

    每个 Account（token + user_id 对）对应一个候选项。
    不使用 asyncio.Lock，依赖事件循环单线程特性保证并发安全。
    """

    def __init__(self) -> None:
        """初始化客户端实例。"""
        self._session: Optional[aiohttp.ClientSession] = None
        self._models: List[str] = []
        self._candidates: List[Candidate] = []

    async def init_immediate(self, session: aiohttp.ClientSession) -> None:
        """立即初始化，不阻塞。

        注入共享会话，构建初始候选项列表。

        Args:
            session: 共享的 aiohttp 会话。

        Returns:
            无返回值。
        """
        self._session = session
        self._rebuild_candidates()
        logger.info(
            "codebuddy 客户端初始化完成，账号数量: %d",
            len(ACCOUNTS),
        )

    async def background_setup(self) -> None:
        """后台完善操作。

        CodeBuddy 平台为静态 token 鉴权，无需登录，此方法为空。

        Returns:
            无返回值。
        """
        return

    def update_models(self, models: List[str]) -> None:
        """更新模型列表，同步刷新所有候选项的 models 字段。

        Args:
            models: 新的模型列表。

        Returns:
            无返回值。
        """
        self._models = list(models)
        for cand in self._candidates:
            cand.models = list(models)

    def _build_candidate(self, account: Account) -> Candidate:
        """根据账号信息构建候选项。

        CodeBuddy 为静态 token，上下文长度未知，填 None。

        Args:
            account: 账号实例。

        Returns:
            候选项实例。
        """
        from src.platforms.codebuddy.adapter import CAPS

        return Candidate(
            id=make_id("codebuddy"),
            platform="codebuddy",
            resource_id=account.token[:12],
            models=list(self._models),
            context_length=account.context_length,
            meta={"token": account.token, "user_id": account.user_id},
            **CAPS,
        )

    def _rebuild_candidates(self) -> None:
        """根据当前账号列表重建候选项列表。

        Returns:
            无返回值。
        """
        self._candidates = [
            self._build_candidate(acc)
            for acc in ACCOUNTS
            if acc.token
        ]

    async def candidates(self) -> List[Candidate]:
        """返回当前候选项列表。

        Returns:
            候选项列表。
        """
        return list(self._candidates)

    async def ensure_candidates(self, count: int) -> int:
        """返回可用候选项数量。

        Args:
            count: 期望的候选项数量（本实现忽略此参数）。

        Returns:
            实际可用候选项数量。
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
            candidate: 候选项。
            messages: 消息列表。
            model: 模型名。
            stream: 是否流式。
            thinking: 是否启用推理。
            search: 是否启用搜索。
            **kw: 额外关键字参数。

        Yields:
            文本片段或元数据字典。

        Raises:
            Exception: 重试耗尽后抛出最后一次异常。
        """
        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                delay = 1.0 * (2 ** (attempt - 1))
                logger.warning(
                    "codebuddy 重试 %d/%d，等待 %.1fs",
                    attempt, MAX_RETRIES, delay,
                )
                await asyncio.sleep(delay)
            try:
                async for chunk in self._do_request(
                    candidate, messages, model, stream,
                ):
                    yield chunk
                return
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "codebuddy 请求失败 %d/%d: %s",
                    attempt + 1, MAX_RETRIES, exc,
                )
        if last_exc is not None:
            raise last_exc

    async def _do_request(
        self,
        candidate: Candidate,
        messages: List[Dict[str, Any]],
        model: str,
        stream: bool,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """执行单次 HTTP 请求。

        Args:
            candidate: 候选项。
            messages: 消息列表。
            model: 模型名。
            stream: 是否流式。

        Yields:
            文本片段或元数据字典。

        Raises:
            Exception: HTTP 状态码非 200 时抛出。
        """
        token = candidate.meta.get("token", "")
        user_id = candidate.meta.get("user_id", "")
        conversation_id = str(uuid.uuid4())
        conversation_request_id = secrets.token_hex(16)
        conversation_message_id = str(uuid.uuid4()).replace("-", "")
        request_id = str(uuid.uuid4()).replace("-", "")
        headers = build_headers(
            token=token,
            user_id=user_id,
            conversation_id=conversation_id,
            conversation_request_id=conversation_request_id,
            conversation_message_id=conversation_message_id,
            request_id=request_id,
        )
        payload = build_payload(messages=messages, model=model, stream=stream)
        url = "{}{}".format(BASE_URL, CHAT_PATH)

        logger.debug(
            "codebuddy 请求: %s model=%s stream=%s messages=%d",
            url, model, stream, len(messages),
        )

        async with self._session.post(
            url,
            json=payload,
            headers=headers,
            ssl=False,
            timeout=aiohttp.ClientTimeout(connect=30, total=300),
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise Exception(
                    "codebuddy HTTP {}: {}".format(resp.status, body[:2000])
                )

            if stream:
                async for chunk in self._handle_stream(resp):
                    yield chunk
            else:
                async for chunk in self._handle_non_stream(resp):
                    yield chunk

    async def _handle_stream(
        self,
        resp: aiohttp.ClientResponse,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """处理流式 SSE 响应。

        对原始字节流进行缓冲和按行拆分，逐行解析 SSE 事件。

        Args:
            resp: aiohttp 响应对象。

        Yields:
            文本片段或元数据字典。
        """
        buffer = ""
        async for raw_chunk in resp.content.iter_any():
            if not raw_chunk:
                continue
            buffer += raw_chunk.decode("utf-8", errors="replace")

            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if not line or line.startswith(":"):
                    continue
                if not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    logger.debug("codebuddy 流结束: [DONE]")
                    return
                parsed = parse_sse_line(data_str)
                if parsed is not None:
                    yield parsed

        # 处理缓冲区中可能残留的最后一行
        remaining = buffer.strip()
        if remaining and remaining.startswith("data:"):
            data_str = remaining[5:].strip()
            if data_str and data_str != "[DONE]":
                parsed = parse_sse_line(data_str)
                if parsed is not None:
                    yield parsed

    async def _handle_non_stream(
        self,
        resp: aiohttp.ClientResponse,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """处理非流式 JSON 响应。

        解析完整 JSON 响应体，提取消息内容和 usage 信息后 yield。

        Args:
            resp: aiohttp 响应对象。

        Yields:
            文本内容或 usage 字典。

        Raises:
            Exception: 响应体包含 error 字段时抛出。
        """
        obj = await resp.json()

        if "error" in obj:
            raise Exception("codebuddy 接口错误: {}".format(obj["error"]))

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
        """清理资源，session 由外部管理，此处不关闭。

        Returns:
            无返回值。
        """
        return
