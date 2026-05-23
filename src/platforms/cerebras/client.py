"""Cerebras HTTP 客户端——同步 SDK 通过 ThreadPoolExecutor 桥接异步"""

from __future__ import annotations

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from src.core.candidate import Candidate, make_id
from src.platforms.cerebras.accounts import API_KEYS
from src.platforms.cerebras.util import (
    build_params,
    extract_delta_content,
    extract_nonstream_content,
    extract_usage,
)

logger = logging.getLogger(__name__)

# 最大重试次数
MAX_RETRIES: int = 3

# 线程池大小（每个 Key 一个线程，保证并发）
_THREAD_POOL_SIZE: int = max(len(API_KEYS), 4)

# 哨兵对象，用于标识流式结束
_SENTINEL = object()


class CerebrasClient:
    """Cerebras 平台 HTTP 客户端。

    使用官方 cerebras-cloud-sdk 同步 SDK，通过 ThreadPoolExecutor
    将同步调用桥接到 asyncio 事件循环。
    """

    def __init__(self) -> None:
        self._session: Any = None
        self._models: List[str] = []
        self._candidates: List[Candidate] = []
        self._executor: Optional[ThreadPoolExecutor] = None

    async def init_immediate(self, session: Any) -> None:
        """立即初始化，不阻塞。

        Args:
            session: 共享 aiohttp ClientSession（Cerebras 使用 SDK，存储备用）。
        """
        self._session = session
        # 创建线程池（同步 SDK 需要）
        self._executor = ThreadPoolExecutor(
            max_workers=_THREAD_POOL_SIZE,
            thread_name_prefix="cerebras",
        )
        # 设置 SSL 环境变量（避免 SDK 内部 SSL 校验失败）
        os.environ.setdefault("SSL_CERT_FILE", "")
        os.environ.setdefault("CURL_CA_BUNDLE", "")
        # 以硬编码列表构建初始候选项
        self._rebuild_candidates()
        logger.info("cerebras 客户端初始化完成，%d 个 Key", len(API_KEYS))

    async def background_setup(self) -> None:
        """后台完善——Cerebras 使用 API Key，无需登录，直接返回。"""
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
        """根据当前 API_KEYS 重建候选项列表。"""
        from src.platforms.cerebras.adapter import CAPS

        self._candidates = [
            Candidate(
                id=make_id("cerebras"),
                platform="cerebras",
                resource_id=key[:12],
                models=list(self._models),
                context_length=None,  # Cerebras 各模型上下文不同，填 None
                meta={"api_key": key},
                **CAPS,
            )
            for key in API_KEYS
            if key
        ]

    async def candidates(self) -> List[Candidate]:
        """返回当前候选项列表。

        Returns:
            当前所有有效候选项的副本列表。
        """
        return list(self._candidates)

    async def ensure_candidates(self, count: int) -> int:
        """返回可用候选项数量。

        Args:
            count: 期望的候选项数量（本实现不扩展）。

        Returns:
            实际可用的候选项数量。
        """
        return len(self._candidates)

    async def fetch_remote_models(self) -> List[str]:
        """通过 SDK 拉取 Cerebras 远程模型列表。

        Returns:
            模型 ID 列表，失败时返回空列表（由 ModelsCache 使用 fallback）。
        """
        if not API_KEYS or self._executor is None:
            return []
        api_key = API_KEYS[0]
        loop = asyncio.get_running_loop()
        try:
            model_ids = await loop.run_in_executor(
                self._executor,
                lambda: self._list_models_sync(api_key),
            )
            logger.info("cerebras 远程模型列表: %d 个", len(model_ids))
            return model_ids
        except Exception as e:
            logger.warning("cerebras 拉取模型列表失败: %s", e)
            return []

    def _list_models_sync(self, api_key: str) -> List[str]:
        """同步拉取模型列表（在线程池中执行）。

        Args:
            api_key: 用于鉴权的 API Key。

        Returns:
            模型 ID 列表。
        """
        from cerebras.cloud.sdk import Cerebras

        client = Cerebras(api_key=api_key)
        models_page = client.models.list()
        return [m.id for m in models_page if hasattr(m, "id")]

    def _make_client(self, api_key: str) -> Any:
        """创建 Cerebras SDK 客户端实例。

        Args:
            api_key: 用于鉴权的 API Key。

        Returns:
            Cerebras SDK 客户端实例。
        """
        from cerebras.cloud.sdk import Cerebras

        return Cerebras(api_key=api_key)

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
            candidate: 选中的候选项（含 API Key）。
            messages: 对话消息列表。
            model: 模型名称。
            stream: 是否流式输出。
            thinking: 推理模式（Cerebras 暂不支持，忽略）。
            search: 搜索模式（Cerebras 暂不支持，忽略）。
            **kw: 其他透传参数（temperature、top_p、max_tokens 等）。

        Yields:
            str 类型的文本片段，或含 usage 键的 dict。

        Raises:
            Exception: 达到最大重试次数后仍失败时抛出最后一次异常。
        """
        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                wait = 1.0 * (2 ** (attempt - 1))
                logger.warning(
                    "cerebras 重试 %d/%d，等待 %.1fs", attempt, MAX_RETRIES, wait
                )
                await asyncio.sleep(wait)
            try:
                async for chunk in self._do_request(
                    candidate, messages, model, stream, **kw
                ):
                    yield chunk
                return
            except Exception as e:
                last_exc = e
                logger.warning(
                    "cerebras 请求失败 attempt=%d: %s", attempt + 1, e
                )
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
        """执行单次 SDK 请求。

        Args:
            candidate: 选中的候选项。
            messages: 对话消息列表。
            model: 模型名称。
            stream: 是否流式输出。
            **kw: 其他参数（temperature、top_p、max_tokens 等）。

        Yields:
            str 类型的文本片段，或含 usage 键的 dict。
        """
        if self._executor is None:
            raise RuntimeError("cerebras client 未初始化，executor 为 None")

        api_key: str = candidate.meta.get("api_key", "")
        params = build_params(
            messages=messages,
            model=model,
            stream=stream,
            temperature=kw.get("temperature", 0.7),
            top_p=kw.get("top_p", 0.8),
            max_tokens=kw.get("max_tokens"),
            frequency_penalty=kw.get("frequency_penalty"),
            presence_penalty=kw.get("presence_penalty"),
            stop=kw.get("stop"),
            user=kw.get("user"),
        )
        loop = asyncio.get_running_loop()

        if not stream:
            resp = await loop.run_in_executor(
                self._executor,
                lambda: self._call_sync(api_key, params),
            )
            content = extract_nonstream_content(resp)
            if content:
                yield content
            if hasattr(resp, "usage") and resp.usage is not None:
                yield {"usage": extract_usage(resp.usage)}
        else:
            queue: asyncio.Queue = asyncio.Queue()

            def _consume() -> None:
                """在线程池中消费流式响应，将 chunk 推入队列。"""
                try:
                    client = self._make_client(api_key)
                    resp = client.chat.completions.create(**params)
                    for chunk in resp:
                        loop.call_soon_threadsafe(queue.put_nowait, chunk)
                except Exception as exc:
                    loop.call_soon_threadsafe(queue.put_nowait, exc)
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, _SENTINEL)

            self._executor.submit(_consume)

            while True:
                item = await queue.get()
                if item is _SENTINEL:
                    break
                if isinstance(item, Exception):
                    logger.error(
                        "cerebras 流式失败 key=%s: %s", api_key[:8], item
                    )
                    raise item
                content = extract_delta_content(item)
                if content:
                    yield content

    def _call_sync(self, api_key: str, params: Dict[str, Any]) -> Any:
        """同步调用 SDK（在线程池中执行）。

        Args:
            api_key: 用于鉴权的 API Key。
            params: SDK create() 所需参数字典。

        Returns:
            SDK 响应对象。
        """
        client = self._make_client(api_key)
        return client.chat.completions.create(**params)

    async def close(self) -> None:
        """清理资源，关闭线程池。"""
        if self._executor is not None:
            self._executor.shutdown(wait=False)
            self._executor = None
