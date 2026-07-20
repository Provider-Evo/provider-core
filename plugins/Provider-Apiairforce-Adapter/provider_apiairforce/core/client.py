
import asyncio
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp

from src.core.dispatch.cand import Candidate, make_id
from src.foundation.logger import get_logger
from .consts import BASE_URL, CAPS, CHAT_PATH, MODELS, MODELS_PATH
from .headers import build_headers
from .payload import build_payload
from .sse import parse_sse_line

logger = get_logger(__name__)

MAX_RETRIES: int = 3
MODEL_CACHE_TTL: int = 24 * 60 * 60  # 24 小时


class Client:
    """apiairforce HTTP 协调器。

    职责限定为协调：账号 / 候选项 / 会话生命周期 / 顶层错误处理与重试。
    """

    def __init__(self) -> None:
        self._session: Optional[aiohttp.ClientSession] = None
        self._models_cache: List[str] = []
        self._models_ts: float = 0.0
        self._candidates: List[Candidate] = []
        self._init_task: Optional[asyncio.Task] = None
        self._api_keys: List[str] = []

    async def init_immediate(self, session: aiohttp.ClientSession) -> None:
        """同步初始化部分：保存 session，构建候选项。"""
        self._session = session
        from ..accounts import API_KEYS
        self._api_keys = list(API_KEYS)
        self._rebuild_candidates()
        logger.info("apiairforce 初始化完成")

    async def init(self, session: aiohttp.ClientSession) -> None:
        """完整初始化入口（供 impl 调用）。"""
        self._session = session
        self._init_task = asyncio.ensure_future(self._background_setup())

    async def _background_setup(self) -> None:
        """后台任务：预热模型缓存。"""
        await self.fetch_remote_models()

    def _rebuild_candidates(self) -> None:
        """根据当前 API keys 重建候选项列表。"""
        models = self._models_cache if self._models_cache else MODELS
        self._candidates = [
            Candidate(
                id=make_id("apiairforce", (key or "public")[:12]),
                platform="apiairforce",
                resource_id=(key or "public")[:12],
                models=list(models),
                meta={"api_key": key},
                chat=True,
                tools=False,
                vision=False,
                thinking=False,
                search=False,
                image_gen=False,
            )
            for key in self._api_keys
        ]

    def candidates(self) -> List[Candidate]:
        """同步返回候选项。"""
        return list(self._candidates)

    def ensure_candidates(self, count: int) -> int:
        """确保候选项数量，返回实际数量。"""
        return len(self._api_keys)

    async def fetch_remote_models(self) -> List[str]:
        """拉取远程模型列表，24 小时缓存。"""
        now = time.time()
        if self._models_cache and now - self._models_ts < MODEL_CACHE_TTL:
            return self._models_cache
        if self._session is None:
            return self._models_cache
        url = f"{BASE_URL}{MODELS_PATH}"
        try:
            async with self._session.get(
                url, headers=build_headers(), ssl=False, timeout=30
            ) as resp:
                if resp.status != 200:
                    logger.warning("apiairforce 拉取模型失败 HTTP %s", resp.status)
                    return self._models_cache
                data = await resp.json()
                items = data.get("data") or []
                models = [m.get("id") for m in items if m.get("id")]
                if models:
                    self._models_cache = models
                    self._models_ts = now
                    self._rebuild_candidates()
        except Exception as e:
            logger.warning("apiairforce 拉取模型异常: %s", e)
        return self._models_cache

    @property
    def supported_models(self) -> List[str]:
        if self._models_cache:
            return list(self._models_cache)
        return MODELS

    async def complete(
        self,
        candidate: Candidate,
        messages: List[Dict[str, Any]],
        model: str,
        stream: bool,
        **kw: Any,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """聊天补全，带重试。"""
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
                logger.warning(
                    "apiairforce 重试 %d/%d: %s", attempt + 1, MAX_RETRIES, e
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
        """执行单次 HTTP 请求。"""
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
                raise Exception(
                    f"apiairforce HTTP {resp.status}: {await resp.text()}"
                )
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
        """关闭客户端。"""
        if self._init_task is not None and not self._init_task.done():
            self._init_task.cancel()
            try:
                await self._init_task
            except (asyncio.CancelledError, Exception) as exc:
                logger.warning("apiairforce 初始化任务取消或失败: %s", exc)
