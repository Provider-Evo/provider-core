from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from src.foundation.config import get_config
from src.core.dispatch.cand import (
    Candidate,
    filter_candidates_by_capability,
    filter_candidates_by_context,
    messages_require_capability,
)
from src.core.dispatch.circuit import get_platform_circuit_breaker
from src.core.dispatch.engine.execs import run_selected
from src.core.dispatch.engine.support.fncall_context import (
    build_dispatch_extra_kw,
    fncall_lang,
    fold_system_into_user,
)
from src.core.dispatch.fback import resolve_fallback_chain
from src.core.utils.errors import NoCandidateError, ProviderError
from src.foundation.observability.metrics import get_metrics_registry

__all__ = ["dispatch"]


def _estimate_prompt_tokens(messages: List[Dict]) -> int:
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        total += _estimate_message_content_tokens(content)
    return total + 64


def _estimate_message_content_tokens(content: Any) -> int:
    """辅助函数：计算单条消息内容的 token 估算值。"""
    if isinstance(content, str):
        return max(1, len(content) // 4)
    elif isinstance(content, list):
        token_count = 0
        for part in content:
            if isinstance(part, dict):
                part_type = part.get("type", "")
                if part_type == "text":
                    token_count += max(1, len(str(part.get("text", ""))) // 4)
                elif part_type in ("image_url", "input_audio"):
                    token_count += 256
        return token_count
    return 0


async def _wait_for_candidates(
    registry: Any, model: str, timeout: float = 15.0, platform: str = "", cfg: Any = None
) -> List[Candidate]:
    deadline = time.monotonic() + timeout
    if cfg is None:
        cfg = get_config()
    breaker = get_platform_circuit_breaker()
    while time.monotonic() < deadline:
        cands = await registry.get_candidates(model)
        if platform:
            cands = [c for c in cands if c.platform == platform]
        cands = [c for c in cands if breaker.allow_platform(c.platform)]
        if cands:
            return cands
        await registry.ensure_candidates(
            model, max(cfg.gateway.concurrent_count, 3)
        )
        await asyncio.sleep(0.5)
    return []


async def _select_dispatch_candidates(
    registry: Any,
    cands: List[Candidate],
    stream: bool,
    cfg: Any = None,
) -> tuple[int, List[Candidate]]:
    if cfg is None:
        cfg = get_config()
    gw = cfg.gateway
    racing_pool = (
        [c for c in cands if gw.is_platform_enabled(c.platform)]
        if gw.group_list_set
        else cands
    )
    n = 1
    if gw.concurrent_enabled and stream and len(racing_pool) > 1 and len(cands) > 1:
        n = min(gw.concurrent_count, len(racing_pool))
    sel_pool = racing_pool if n > 1 else cands
    sel = await registry.selector.select(sel_pool, n)
    if not sel:
        raise NoCandidateError("TAS 选择失败")
    return n, sel


async def _filter_dispatch_candidates(
    cands: List[Candidate],
    messages: List[Dict],
    model: str,
    max_tokens: Optional[int],
) -> List[Candidate]:
    """按上下文容量、chat/vision 能力对候选项进行过滤。"""
    reserve = (max_tokens or 0) + 256
    min_ctx = _estimate_prompt_tokens(messages) + reserve
    filtered = filter_candidates_by_context(cands, model, min_ctx)
    if not filtered:
        filtered = cands
    cands = filtered

    chat_filtered = filter_candidates_by_capability(cands, model, "chat")
    if chat_filtered:
        cands = chat_filtered

    if messages_require_capability(messages, "vision"):
        cap_filtered = filter_candidates_by_capability(cands, model, "vision")
        if cap_filtered:
            cands = cap_filtered

    return cands


async def _resolve_dispatch_selection(
    registry: Any,
    messages: List[Dict],
    model: str,
    stream: bool,
    max_tokens: Optional[int],
    platform: str,
    cfg: Any,
) -> List[Candidate]:
    """等待候选项就绪、按上下文/能力过滤，并执行 TAS 选择。"""
    cands = await _wait_for_candidates(registry, model, timeout=15.0, platform=platform, cfg=cfg)
    if not cands:
        raise NoCandidateError("无候选项: {}".format(model))

    cands = await _filter_dispatch_candidates(cands, messages, model, max_tokens)

    _n, sel = await _select_dispatch_candidates(registry, cands, stream, cfg=cfg)
    return sel


async def _dispatch_model(
    registry: Any,
    messages: List[Dict],
    model: str,
    stream: bool,
    *,
    tools: Optional[List[Dict]] = None,
    thinking: bool = False,
    search: bool = False,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    max_tokens: Optional[int] = None,
    stop: Optional[List[str]] = None,
    upload_files: Optional[List[Any]] = None,
    platform: str = "",
    **kw: Any,
) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
    final_msgs = fold_system_into_user(messages, tools)
    cfg = get_config()

    sel = await _resolve_dispatch_selection(
        registry, messages, model, stream, max_tokens, platform, cfg,
    )

    extra_kw = build_dispatch_extra_kw(
        kw,
        upload_files=upload_files,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        stop=stop,
    )

    async for chunk in run_selected(
        registry,
        sel,
        final_msgs,
        model,
        stream,
        thinking,
        search,
        tools,
        fncall_lang(kw),
        kw.get("protocol_id", ""),
        extra_kw,
    ):
        yield chunk


async def _run_gateway_before_hook(
    registry: Any,
    messages: List[Dict],
    model: str,
    stream: bool,
    platform: str,
    tools: Optional[List[Dict]],
) -> tuple[List[Dict], str, str]:
    """执行 gateway.request.before hook，返回可能被 hook 改写后的 messages/model/platform。"""
    from src.core.utils.errors import GatewayAbortedError
    from src.core.server.http.request_context import get_api_token
    from src.core.server.plugins.hook_reg import get_hook_registry

    hook_ctx = {
        "registry": registry,
        "messages": messages,
        "model": model,
        "stream": stream,
        "platform": platform,
        "tools": tools,
        "api_token": get_api_token() or "",
    }
    before = await get_hook_registry().invoke("gateway.request.before", hook_ctx)
    if before.aborted:
        raise GatewayAbortedError(before.abort_reason or "gateway.request.before aborted")
    messages = list(before.context.get("messages", messages))
    model = str(before.context.get("model", model))
    platform = str(before.context.get("platform", platform))
    return messages, model, platform


async def _run_gateway_after_hook(
    registry: Any,
    attempt_model: str,
    stream: bool,
    platform: str,
    sel_count: int,
) -> None:
    from src.core.server.plugins.hook_reg import get_hook_registry

    await get_hook_registry().invoke(
        "gateway.request.after",
        {
            "registry": registry,
            "model": attempt_model,
            "stream": stream,
            "platform": platform,
            "candidate_count": sel_count,
        },
    )


async def _try_dispatch_attempt(
    registry: Any,
    messages: List[Dict],
    attempt_model: str,
    stream: bool,
    metrics: Any,
    start: float,
    platform: str,
    sel_count: int,
    tools: Optional[List[Dict]],
    thinking: bool,
    search: bool,
    temperature: Optional[float],
    top_p: Optional[float],
    max_tokens: Optional[int],
    stop: Optional[List[str]],
    upload_files: Optional[List[Any]],
    kw: Dict[str, Any],
) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
    """尝试对单个 Fallback 模型执行分发，成功后触发 after-hook。"""
    async for chunk in _dispatch_model(
        registry,
        messages,
        attempt_model,
        stream,
        tools=tools,
        thinking=thinking,
        search=search,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        stop=stop,
        upload_files=upload_files,
        platform=platform,
        **kw,
    ):
        yield chunk
    metrics.inc_success()
    metrics.observe_latency_ms((time.monotonic() - start) * 1000)
    await _run_gateway_after_hook(registry, attempt_model, stream, platform, sel_count)


async def dispatch(
    registry: Any,
    messages: List[Dict],
    model: str,
    stream: bool,
    *,
    tools: Optional[List[Dict]] = None,
    thinking: bool = False,
    search: bool = False,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    max_tokens: Optional[int] = None,
    stop: Optional[List[str]] = None,
    upload_files: Optional[List[Any]] = None,
    platform: str = "",
    **kw: Any,
) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
    """核心分发：Fallback 链 + 单发/竞速执行。"""
    messages, model, platform = await _run_gateway_before_hook(
        registry, messages, model, stream, platform, tools
    )

    metrics = get_metrics_registry()
    metrics.inc_requests()
    start = time.monotonic()
    last_err: Optional[Exception] = None
    sel_count = 0

    for attempt_model in resolve_fallback_chain(model):
        try:
            async for chunk in _try_dispatch_attempt(
                registry, messages, attempt_model, stream, metrics, start,
                platform, sel_count, tools, thinking, search, temperature,
                top_p, max_tokens, stop, upload_files, kw,
            ):
                yield chunk
            return
        except (NoCandidateError, ProviderError) as exc:
            last_err = exc
            metrics.inc_fallback()
            continue

    metrics.inc_failure()
    if last_err is not None:
        raise last_err
    raise NoCandidateError("所有 Fallback 模型均无候选项: {}".format(model))
