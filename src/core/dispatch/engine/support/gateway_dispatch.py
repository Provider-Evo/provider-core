"""Gateway 模型分发与 Fallback 链执行。"""

from __future__ import annotations

import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from src.core.dispatch.engine.execs import run_selected
from src.core.dispatch.engine.support.fncall_context import (
    build_dispatch_extra_kw,
    fold_system_into_user,
    fncall_lang,
)
from src.core.dispatch.fback import resolve_fallback_chain
from src.core.utils.errors import (
    ContextLengthError,
    ModerationError,
    NoCandidateError,
    ProviderError,
)
from src.foundation.config import get_config
from src.foundation.observability.metrics import get_metrics_registry


async def dispatch_model(
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
    from src.core.dispatch.engine.gateway import _resolve_dispatch_selection

    final_msgs = fold_system_into_user(messages, tools)
    cfg = get_config()
    sel = await _resolve_dispatch_selection(
        registry, messages, model, stream, max_tokens, platform, cfg
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


async def try_dispatch_attempt(
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
    from src.core.dispatch.engine.gateway import _run_gateway_after_hook

    async for chunk in dispatch_model(
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


async def _yield_fallback_chain(
    registry: Any,
    messages: List[Dict],
    model: str,
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
    last_err: Optional[Exception] = None
    for attempt_model in resolve_fallback_chain(model):
        try:
            async for chunk in try_dispatch_attempt(
                registry, messages, attempt_model, stream, metrics, start,
                platform, sel_count, tools, thinking, search, temperature,
                top_p, max_tokens, stop, upload_files, kw,
            ):
                yield chunk
            return
        except (NoCandidateError, ProviderError) as exc:
            if isinstance(exc, (ModerationError, ContextLengthError)):
                raise
            last_err = exc
            metrics.inc_fallback()
            continue
    metrics.inc_failure()
    if last_err is not None:
        raise last_err
    raise NoCandidateError("所有 Fallback 模型均无候选项: {}".format(model))


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
    from src.core.dispatch.engine.gateway import _run_gateway_before_hook

    messages, model, platform = await _run_gateway_before_hook(
        registry, messages, model, stream, platform, tools
    )
    metrics = get_metrics_registry()
    metrics.inc_requests()
    start = time.monotonic()
    async for chunk in _yield_fallback_chain(
        registry,
        messages,
        model,
        stream,
        metrics,
        start,
        platform,
        0,
        tools,
        thinking,
        search,
        temperature,
        top_p,
        max_tokens,
        stop,
        upload_files,
        kw,
    ):
        yield chunk
