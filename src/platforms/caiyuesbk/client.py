"""caiyuesbk 客户端——使用 fncall 注入协议"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp

from src.core.candidate import Candidate, make_id
from src.platforms.caiyuesbk.accounts import API_KEYS
from src.platforms.caiyuesbk.util import (
    BASE_URL,
    CHAT_PATH,
    build_headers,
    build_payload,
    make_ssl_ctx,
    parse_sse_line,
)

logger = logging.getLogger(__name__)

MAX_RETRIES: int = 3
_SSL_CTX = make_ssl_ctx()


class CaiyuesbkClient:
    """caiyuesbk HTTP 客户端。"""

    def __init__(self) -> None:
        self._session: Optional[aiohttp.ClientSession] = None
        self._models: List[str] = []
        self._candidates: List[Candidate] = []

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def init_immediate(self, session: aiohttp.ClientSession) -> None:
        """立即初始化，存储 session 并构建初始候选项，不阻塞。

        Args:
            session: 共享的 aiohttp 客户端会话。
        """
        self._session = session
        self._rebuild_candidates()
        logger.info("caiyuesbk 客户端初始化完成: %d keys", len(API_KEYS))

    async def background_setup(self) -> None:
        """后台完善：并发验证所有 API Key 的有效性，更新候选项状态。"""
        if not self._session:
            return

        results = await asyncio.gather(
            *[self._test_key(key) for key in API_KEYS],
            return_exceptions=True,
        )

        # 根据测试结果更新候选项 available 状态
        for cand, result in zip(self._candidates, results):
            if isinstance(result, Exception):
                cand.available = False
                logger.warning(
                    "caiyuesbk key 验证异常 %s: %s",
                    cand.resource_id,
                    result,
                )
            else:
                cand.available = bool(result)

        available_count = sum(1 for c in self._candidates if c.available)
        logger.info(
            "caiyuesbk 后台验证完成: %d/%d keys 可用",
            available_count,
            len(self._candidates),
        )

    async def close(self) -> None:
        """清理资源（session 由外部管理，此处不关闭）。"""
        return

    # ------------------------------------------------------------------
    # 模型管理
    # ------------------------------------------------------------------

    def update_models(self, models: List[str]) -> None:
        """更新模型列表，同步刷新所有候选项的 models 字段。

        Args:
            models: 新的模型列表。
        """
        self._models = list(models)
        for cand in self._candidates:
            cand.models = list(models)

    async def fetch_models(self) -> List[str]:
        """从远程 API 拉取当前可用模型列表。

        Returns:
            模型 ID 列表。

        Raises:
            RuntimeError: session 未初始化时抛出。
            Exception: HTTP 请求失败时抛出。
        """
        if not self._session:
            raise RuntimeError("Client not initialized")

        # 使用第一个可用 key 拉取模型列表
        api_key = self._get_active_key()
        if not api_key:
            raise RuntimeError("no active api key available")

        url = "{}/v1/models".format(BASE_URL)
        async with self._session.get(
            url,
            headers=build_headers(api_key),
            ssl=_SSL_CTX,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status != 200:
                raise Exception(
                    "caiyuesbk /v1/models HTTP {}: {}".format(
                        resp.status, await resp.text()
                    )
                )
            data = await resp.json()
            model_ids: List[str] = [
                item["id"]
                for item in data.get("data", [])
                if isinstance(item, dict) and item.get("id")
            ]
            return model_ids

    # ------------------------------------------------------------------
    # 候选项管理
    # ------------------------------------------------------------------

    def _rebuild_candidates(self) -> None:
        """根据当前 API_KEYS 重建候选项列表。"""
        from src.platforms.caiyuesbk.adapter import CAPS

        self._candidates = [
            Candidate(
                id=make_id("caiyuesbk"),
                platform="caiyuesbk",
                resource_id=key[:12],
                models=list(self._models),
                # caiyuesbk 多模型上下文各异，填 None 表示未知
                context_length=None,
                available=True,
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
        """返回当前候选项数量。

        Args:
            count: 期望数量（此实现忽略该参数，返回实际数量）。

        Returns:
            当前候选项数量。
        """
        return len(self._candidates)

    # ------------------------------------------------------------------
    # 聊天补全
    # ------------------------------------------------------------------

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
        """执行聊天补全请求，含指数退避重试。

        Args:
            candidate: 选中的候选项（含 api_key）。
            messages: 对话消息列表。
            model: 模型名称。
            stream: 是否流式响应。
            thinking: 是否启用思考模式（参数透传，caiyuesbk 通过 fncall 处理）。
            search: 是否启用搜索增强（参数透传）。
            **kw: 其他透传参数（temperature、top_p、max_tokens、stop）。

        Yields:
            文本增量（str）或元数据字典（dict，含 usage 键）。

        Raises:
            Exception: 超过最大重试次数后抛出最后一次异常。
        """
        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                wait = 1.0 * (2 ** (attempt - 1))
                logger.warning(
                    "caiyuesbk 第 %d/%d 次重试，等待 %.1fs",
                    attempt,
                    MAX_RETRIES,
                    wait,
                )
                await asyncio.sleep(wait)
            try:
                async for chunk in self._do_request(
                    candidate, messages, model, stream, **kw
                ):
                    yield chunk
                return
            except Exception as exc:
                last_exc = exc
                logger.warning("caiyuesbk 请求失败 (attempt %d): %s", attempt, exc)

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
        """执行单次 HTTP 请求。

        Args:
            candidate: 候选项（含 api_key）。
            messages: 消息列表。
            model: 模型名称。
            stream: 是否流式。
            **kw: 可选参数（temperature、top_p、max_tokens、stop）。

        Yields:
            文本增量（str）或元数据字典（dict）。

        Raises:
            RuntimeError: session 未初始化。
            asyncio.TimeoutError: 请求超时。
            Exception: HTTP 非 200 状态或其他网络错误。
        """
        if not self._session:
            raise RuntimeError("Client not initialized")

        api_key: str = candidate.meta["api_key"]
        headers = build_headers(api_key)
        payload = build_payload(
            messages,
            model,
            stream,
            temperature=kw.get("temperature"),
            top_p=kw.get("top_p"),
            max_tokens=kw.get("max_tokens"),
            stop=kw.get("stop"),
        )
        url = "{}{}".format(BASE_URL, CHAT_PATH)

        try:
            async with self._session.post(
                url,
                json=payload,
                headers=headers,
                ssl=_SSL_CTX,
                timeout=aiohttp.ClientTimeout(connect=10, total=300),
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(
                        "caiyuesbk 请求失败 %s: HTTP %d %s",
                        api_key[:8],
                        resp.status,
                        error_text[:200],
                    )
                    raise Exception(
                        "caiyuesbk HTTP {}: {}".format(resp.status, error_text[:100])
                    )

                if stream:
                    async for chunk in self._read_stream(resp, api_key):
                        yield chunk
                else:
                    async for chunk in self._read_non_stream(resp):
                        yield chunk

        except asyncio.TimeoutError:
            logger.error(
                "caiyuesbk 请求超时 %s (stream=%s)", api_key[:8], stream
            )
            raise

    async def _read_stream(
        self,
        resp: aiohttp.ClientResponse,
        api_key: str,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """读取流式 SSE 响应。

        Args:
            resp: aiohttp 响应对象。
            api_key: 当前使用的 API Key（用于日志）。

        Yields:
            文本增量（str）或 usage 字典（dict）。
        """
        async for raw_line in resp.content:
            if not raw_line:
                continue
            line_str = raw_line.decode("utf-8", errors="replace").strip()
            if not line_str or not line_str.startswith("data:"):
                continue
            data_str = line_str[5:].strip()
            if data_str == "[DONE]":
                break
            parsed = parse_sse_line(data_str)
            if parsed is not None:
                yield parsed

    async def _read_non_stream(
        self,
        resp: aiohttp.ClientResponse,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """读取非流式 JSON 响应。

        Args:
            resp: aiohttp 响应对象。

        Yields:
            文本内容（str）和可选的 usage 字典（dict）。
        """
        data = await resp.json()
        choices = data.get("choices")
        if choices:
            msg = choices[0].get("message", {})
            content = msg.get("content", "")
            if content:
                yield content
        usage = data.get("usage")
        if usage:
            yield {"usage": usage}

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _get_active_key(self) -> Optional[str]:
        """获取第一个可用候选项的 API Key。

        Returns:
            API Key 字符串，无可用候选项时返回 None。
        """
        for cand in self._candidates:
            if cand.available:
                return cand.meta.get("api_key")
        # 兜底：返回第一个 key（即使标记为不可用）
        if self._candidates:
            return self._candidates[0].meta.get("api_key")
        return None

    async def _test_key(self, api_key: str) -> bool:
        """测试单个 API Key 是否有效。

        Args:
            api_key: 待测试的 API Key。

        Returns:
            True 表示 key 有效，False 表示无效或请求失败。
        """
        if not self._session:
            return False
        try:
            async with self._session.get(
                "{}/v1/models".format(BASE_URL),
                headers=build_headers(api_key),
                ssl=_SSL_CTX,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                return resp.status == 200
        except Exception as exc:
            logger.debug("caiyuesbk key 测试失败 %s: %s", api_key[:8], exc)
            return False
