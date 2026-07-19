from __future__ import annotations

"""Nvidia HTTP 客户端。"""

import asyncio
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp

from src.core.dispatch.cand import Candidate, make_id
from src.core.utils.errors import PlatformError
from src.foundation.logger import get_logger
from .helpers.client_helpers import (
    KeyState as _KeyState,
    build_chat_request,
    dispatch_response,
)

logger = get_logger(__name__)

MAX_RETRIES: int = 3


class NvidiaClient:
    """Nvidia HTTP 客户端。

    职责限定为协调：账号/候选项/会话生命周期/顶层错误处理与重试。
    具体的Key状态、请求构造与响应解析拆分至 ``client_helpers.py``。
    """

    def __init__(self) -> None:
        self._session: Optional[aiohttp.ClientSession] = None
        self._models: List[str] = []
        self._keys: List[_KeyState] = []
        self._candidates: List[Candidate] = []

    async def init_immediate(self, session: aiohttp.ClientSession) -> None:
        """立即初始化，不阻塞。

        Args:
            session: 共享的 aiohttp ClientSession。
        """
        self._session = session
        from ..accounts import API_KEYS

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
        from .consts import CAPS

        self._candidates = [
            Candidate(
                id=make_id("nvidia", ks.key[:16]),
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
        """根据候选项找到对应的KeyState。

        Args:
            candidate: 候选项对象。

        Returns:
            匹配的KeyState或None。
        """
        api_key = candidate.meta.get("api_key", "")
        for ks in self._keys:
            if ks.key == api_key:
                return ks
        return None

    async def candidates(self) -> List[Candidate]:
        """返回当前候选项列表。

        Returns:
            可用候选项列表。
        """
        from .consts import CAPS

        return [
            Candidate(
                id=make_id("nvidia", ks.key[:16]),
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
        """返回可用候选项数量。

        Args:
            count: 期望的数量（Nvidia仅返回实际值）。

        Returns:
            可用候选项数量。
        """
        return sum(1 for ks in self._keys if ks.available)

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
        """执行聊天补全，含重试。

        Args:
            candidate: 选中的候选项。
            messages: 对话消息列表。
            model: 模型名。
            stream: 是否流式输出。
            thinking: 是否启用思考模式。
            search: 是否启用搜索。
            **kw: 额外参数。

        Yields:
            文本片段(str)或结构化数据(dict)。
        """
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

    async def _send_and_dispatch(
        self,
        url: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
        stream: bool,
        ks: Any,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """发送单次 HTTP 请求并分发响应，从 ``_do_request`` 抽出。"""
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
            async for chunk in dispatch_response(resp, stream, ks):
                yield chunk
            ks.mark_success()

    async def _do_request(
        self,
        candidate: Candidate,
        messages: List[Dict[str, Any]],
        model: str,
        stream: bool,
        **kw: Any,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """执行单次HTTP请求。

        Raises:
            PlatformError: 请求失败时抛出。
        """
        ks = self._find_key(candidate)
        if not ks:
            raise PlatformError("nvidia: 未找到对应APIKey")

        url, headers, payload = build_chat_request(
            ks, messages, model, stream, **kw
        )

        ks.busy = True
        try:
            async for chunk in self._send_and_dispatch(url, headers, payload, stream, ks):
                yield chunk
        except PlatformError:
            raise
        except Exception as e:
            ks.mark_failure(0)
            raise PlatformError("nvidia请求失败: {}".format(e)) from e

    async def close(self) -> None:
        """清理资源。"""
        return
