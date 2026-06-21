from __future__ import annotations

# src/platforms/deepseek/core/client.py
"""DeepSeek HTTP 客户端——管理账号登录、PoW、HIF、流式补全"""

import asyncio
import secrets
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from src.logger import get_logger

import aiohttp

from src.platforms.deepseek.accounts import ACCOUNTS, Account
from src.platforms.deepseek.core.constants import (
    CAPS,
    DEFAULT_HOST,
    HIF_REFRESH_INTERVAL,
    MAX_CONTINUE,
    MAX_RETRIES,
    MODEL_FLASH,
    MODEL_PRO,
    MODEL_TYPE_MAP,
    MODEL_VISION,
    MODELS,
)
from src.platforms.deepseek.core.headers import build_headers
from src.platforms.deepseek.core.hif import HifTokenManager, fetch_hif_tokens
from src.platforms.deepseek.core.pow import WasmPow, download_wasm, get_pow_response
from src.platforms.deepseek.core.sessionapi import create_session
from src.platforms.deepseek.core.streamparser import StreamParser
from src.platforms.deepseek.core.userapi import login
from src.core.dispatch.candidate import Candidate, make_id

logger = get_logger(__name__)


def make_stream_id() -> str:
    """生成流式请求 ID。

    Returns:
        格式为 YYYYMMDD-{8位十六进制} 的字符串。
    """
    return "{}-{}".format(
        datetime.now().strftime("%Y%m%d"),
        secrets.token_hex(8),
    )


def _build_prompt(messages: List[Dict[str, Any]]) -> str:
    """将 OpenAI 格式消息列表转为 DeepSeek 单 prompt 字符串。

    Args:
        messages: OpenAI 格式消息列表。

    Returns:
        拼接后的提示文本。
    """
    parts: List[str] = []
    for m in messages:
        role = m.get("role", "user")
        c = m.get("content", "")
        if isinstance(c, list):
            c = "\n".join(
                p.get("text", "")
                for p in c
                if isinstance(p, dict) and p.get("type") == "text"
            )
        if role == "system":
            parts.append("系统指令: {}".format(c))
        elif role == "user":
            parts.append("用户: {}".format(c))
        elif role == "assistant":
            parts.append("助手: {}".format(c))
        elif role == "tool":
            parts.append("工具结果: {}".format(c))
    return "\n\n".join(parts)


def _translate_chunk(chunk: Dict[str, Any]) -> Optional[Union[str, Dict[str, Any]]]:
    """将内部 chunk 转换为 yield 协议格式。

    Args:
        chunk: 内部 chunk 字典。

    Returns:
        str（正文增量）、dict（thinking/usage）或 None。
    """
    t = chunk.get("type")
    if t == "content":
        content = chunk.get("content", "")
        return content if content else None
    if t == "thinking":
        content = chunk.get("content", "")
        return {"thinking": content} if content else None
    return None


def _model_supports_thinking_and_search(model: str) -> bool:
    """判断模型是否支持联网搜索和思考功能。

    根据文档：deepseek-v4-pro 和 deepseek-v4-flash 均支持联网和思考设置。

    Args:
        model: 模型名称。

    Returns:
        是否支持。
    """
    return model in (MODEL_PRO, MODEL_FLASH)


# ── 客户端主类 ─────────────────────────────────────────────────────────────────

class DeepseekClient:
    """DeepSeek HTTP 客户端（管理账号登录、PoW、HIF、流式补全）。"""

    def __init__(self) -> None:
        """初始化客户端。"""
        self._session: Optional[aiohttp.ClientSession] = None
        self._pow: WasmPow = WasmPow()
        self._models: List[str] = list(MODELS)
        self._candidates: List[Any] = []
        # 每个账号对应一个 HIF 令牌管理器
        self._hif_managers: Dict[str, HifTokenManager] = {}
        self._proxy_override: Optional[bool] = None
        self._closing: bool = False

    async def init_immediate(self, session: aiohttp.ClientSession) -> None:
        """立即初始化（不阻塞）。

        Args:
            session: 共享的 aiohttp ClientSession。
        """
        self._session = session
        # 为每个账号预建 HIF 管理器
        for account in ACCOUNTS:
            mgr = HifTokenManager()
            mgr.bind_session(session)
            self._hif_managers[account.username] = mgr
        self._rebuild_candidates()
        logger.info("deepseek 客户端已初始化（等待后台登录）")

    def set_proxy_enabled(self, enabled: bool) -> None:
        """设置此平台的代理覆盖开关。

        Args:
            enabled: True 强制使用代理，False 强制不使用。
        """
        self._proxy_override = bool(enabled)

    def is_proxy_enabled(self) -> bool:
        """返回此平台当前是否启用代理覆盖。

        Returns:
            是否启用代理。
        """
        return bool(self._proxy_override)

    def _get_proxy_kwarg(self) -> Optional[str]:
        """获取应传递给 session.request 的 proxy 值。"""
        if self._proxy_override is True:
            from src.core.server import get_proxy_server
            return get_proxy_server()
        return None

    async def background_setup(self) -> None:
        """后台完善：下载 WASM 并并发登录所有账号。"""
        asyncio.ensure_future(download_wasm(self._session))
        asyncio.ensure_future(self._bg_wasm_check())
        asyncio.ensure_future(self._bg_hif_refresh())

        tasks = [
            asyncio.ensure_future(self._login_account(account))
            for account in ACCOUNTS
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for account, result in zip(ACCOUNTS, results):
            if isinstance(result, Exception):
                logger.error("deepseek 登录失败 %s: %s", account.username, result)

    async def _bg_wasm_check(self) -> None:
        """后台每 24 小时检查并更新 WASM。"""
        while not self._closing:
            await asyncio.sleep(86400)
            if self._closing:
                break
            try:
                await download_wasm(self._session)
                self._pow = WasmPow()
            except Exception as exc:
                logger.warning("WASM 更新失败: %s", exc)

    async def _bg_hif_refresh(self) -> None:
        """后台每隔一段时间刷新所有账号的 HIF 令牌。"""
        while True:
            await asyncio.sleep(HIF_REFRESH_INTERVAL)
            for account in ACCOUNTS:
                if not account.token:
                    continue
                mgr = self._hif_managers.get(account.username)
                if mgr is None:
                    continue
                try:
                    leim, dliq, expire = await fetch_hif_tokens(self._session)
                    mgr._leim = leim
                    mgr._dliq = dliq
                    mgr._expire_at = expire
                except Exception as exc:
                    logger.warning("HIF 刷新失败 %s: %s", account.username, exc)

    async def _login_account(self, account: Account) -> None:
        """登录单个账号并更新 token。

        Args:
            account: 账号对象。
        """
        token, user_id = await login(
            self._session, account.username, account.password
        )
        account.token = token
        account.user_id = user_id
        logger.info("deepseek 登录成功: %s (id=%s)", account.username, user_id)

        # 立即获取 HIF 令牌
        mgr = self._hif_managers.get(account.username)
        if mgr is not None:
            try:
                leim, dliq, expire = await fetch_hif_tokens(self._session)
                mgr._leim = leim
                mgr._dliq = dliq
                mgr._expire_at = expire
            except Exception as exc:
                logger.warning("首次 HIF 令牌获取失败 %s: %s", account.username, exc)

        self._rebuild_candidates()

    def update_models(self, models: List[str]) -> None:
        """更新模型列表，同步刷新所有候选项的 models 字段。

        Args:
            models: 新的模型列表。
        """
        self._models = list(models)
        for cand in self._candidates:
            cand.models = list(models)

    def _rebuild_candidates(self) -> None:
        """根据当前账号状态重建候选项列表。"""
        self._candidates = [
            Candidate(
                id=make_id("deepseek", account.username[:20]),
                platform="deepseek",
                resource_id=account.username[:20],
                models=list(self._models),
                context_length=account.context_length,
                meta={
                    "identifier": account.username,
                    "token": account.token,
                    "user_id": account.user_id,
                },
                **CAPS,
            )
            for account in ACCOUNTS
            if account.token
        ]

    async def candidates(self) -> List[Any]:
        """返回当前候选项列表。

        Returns:
            候选项列表。
        """
        return list(self._candidates)

    async def ensure_candidates(self, count: int) -> int:
        """返回可用候选项数量。

        Args:
            count: 期望数量（此处仅返回当前实际数量）。

        Returns:
            当前可用候选项数量。
        """
        return len(self._candidates)

    async def complete(
        self,
        candidate: Any,
        messages: List[Dict[str, Any]],
        model: str,
        stream: bool,
        *,
        thinking: bool = False,
        search: bool = False,
        **kw: Any,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """执行聊天补全（含重试）。

        Args:
            candidate: 候选项。
            messages: 消息列表。
            model: 模型名（deepseek-v4-pro / deepseek-v4-flash / deepseek-v4-vision）。
            stream: 是否流式。
            thinking: 是否启用思考模式（两个模型均支持）。
            search: 是否启用联网搜索（两个模型均支持）。
            **kw: 额外参数透传。

        Yields:
            str（文本增量）或 dict（thinking/usage）。
        """
        supports_ts = _model_supports_thinking_and_search(model)
        effective_thinking = thinking and supports_ts
        effective_search = search and supports_ts

        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                await asyncio.sleep(1.0 * (2 ** (attempt - 1)))
            try:
                async for chunk in self._do_complete(
                    candidate,
                    messages,
                    model,
                    stream,
                    thinking=effective_thinking,
                    search=effective_search,
                ):
                    yield chunk
                return
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "deepseek 重试 %d/%d: %s", attempt + 1, MAX_RETRIES, exc
                )
        if last_exc:
            raise last_exc

    async def _do_complete(
        self,
        candidate: Any,
        messages: List[Dict[str, Any]],
        model: str,
        stream: bool,
        *,
        thinking: bool = False,
        search: bool = False,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """执行单次完整会话请求。

        Args:
            candidate: 候选项（含 token）。
            messages: 消息列表。
            model: 模型名。
            stream: 是否流式。
            thinking: 是否启用思考模式。
            search: 是否启用联网搜索。

        Yields:
            str（文本增量）或 dict（thinking/usage）。
        """
        token = candidate.meta.get("token", "")
        username = candidate.meta.get("identifier", "")

        # 获取 HIF 令牌
        mgr = self._hif_managers.get(username)
        hif_leim = ""
        hif_dliq = ""
        if mgr is not None:
            hif_leim, hif_dliq = await mgr.ensure_valid()

        # 获取 PoW 响应
        pow_resp = ""
        if self._pow.available:
            pow_resp = await get_pow_response(
                self._session, token, self._pow, "/api/v0/chat/completion"
            )

        # 创建会话
        session_id = await create_session(self._session, token)

        # 构建提示词
        prompt = _build_prompt(messages)

        # 确定内部 model_type
        model_type = MODEL_TYPE_MAP.get(model, "default")

        # 构建请求头
        req_headers = build_headers(
            token=token,
            session_id=session_id,
            hif_leim=hif_leim,
            hif_dliq=hif_dliq,
            pow_response=pow_resp,
        )

        payload_thinking = False if model == MODEL_VISION else thinking
        payload_search = False if model == MODEL_VISION else search
        payload: Dict[str, Any] = {
            "chat_session_id": session_id,
            "parent_message_id": None,
            "model_type": model_type,
            "prompt": prompt,
            "ref_file_ids": [],
            "thinking_enabled": payload_thinking,
            "search_enabled": payload_search,
            "preempt": False,
            "client_stream_id": make_stream_id(),
        }

        parser = StreamParser(include_thinking=payload_thinking)
        needs_continue = False

        url = "https://{}/api/v0/chat/completion".format(DEFAULT_HOST)
        post_kw: Dict[str, Any] = {
            "headers": req_headers,
            "json": payload,
            "timeout": aiohttp.ClientTimeout(total=600),
            "ssl": False,
        }
        if self._proxy_override is not None:
            post_kw["proxy"] = self._get_proxy_kwarg()

        parser.begin_stream(is_continuation=False)
        async with self._session.post(url, **post_kw) as resp:
            if resp.status != 200:
                raise Exception("聊天失败 HTTP {}".format(resp.status))

            async for chunk in self._parse_sse_stream(resp, parser):
                if chunk.get("needs_continue"):
                    needs_continue = True
                elif chunk.get("type") not in ("event", "status"):
                    translated = _translate_chunk(chunk)
                    if translated is not None:
                        yield translated

        needs_continue = needs_continue or parser.should_continue

        # 处理 continue（截断续写）
        continue_count = 0
        while needs_continue and continue_count < MAX_CONTINUE:
            continue_count += 1
            mid = parser.message_id
            if mid is None:
                break
            await asyncio.sleep(0.1)

            cont_headers = build_headers(
                token=token,
                session_id=session_id,
                hif_leim=hif_leim,
                hif_dliq=hif_dliq,
            )
            cont_payload = {
                "chat_session_id": session_id,
                "message_id": mid,
                "fallback_to_resume": True,
            }
            parser.begin_stream(is_continuation=True)
            async with self._session.post(
                "https://{}/api/v0/chat/continue".format(DEFAULT_HOST),
                headers=cont_headers,
                json=cont_payload,
                timeout=aiohttp.ClientTimeout(total=600),
                ssl=False,
            ) as cont_resp:
                if cont_resp.status != 200:
                    break
                needs_continue = False
                async for chunk in self._parse_sse_stream(cont_resp, parser):
                    if chunk.get("needs_continue"):
                        needs_continue = True
                    elif chunk.get("type") not in ("event", "status"):
                        translated = _translate_chunk(chunk)
                        if translated is not None:
                            yield translated
                needs_continue = needs_continue or parser.should_continue

        # 输出 usage 统计
        content_len = len(parser.accumulated_content)
        think_len = len(parser.accumulated_thinking)
        total_chars = content_len + think_len
        prompt_tokens = max(len(prompt) // 3, 1)
        completion_tokens = max(total_chars // 3, 0)
        yield {
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            }
        }

    async def _parse_sse_stream(
        self,
        resp: Any,
        parser: StreamParser,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """解析 SSE 流式响应。

        Args:
            resp: aiohttp 响应对象。
            parser: StreamParser 实例。

        Yields:
            解析后的 chunk 字典。
        """
        buf = ""
        async for raw_chunk in resp.content.iter_chunked(4096):
            if raw_chunk:
                buf += raw_chunk.decode("utf-8", errors="ignore")
                lines = buf.split("\n")
                buf = lines[-1]
                for line in lines[:-1]:
                    if line.strip():
                        result = parser.parse_line(line)
                        if result is not None:
                            yield result
        # 处理剩余缓冲区
        if buf.strip():
            result = parser.parse_line(buf)
            if result is not None:
                yield result

    async def close(self) -> None:
        """清理资源（客户端本身不拥有 session，不关闭）。"""
        self._closing = True
