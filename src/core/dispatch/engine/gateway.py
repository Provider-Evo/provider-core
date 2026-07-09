from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from src.core.dispatch.candidate import Candidate
from src.core.config import get_config
from src.core.dispatch.engine.executors import run_selected
from src.core.dispatch.engine.fncall_context import (
    build_dispatch_extra_kw,
    fncall_lang,
    fold_system_into_user,
)
from src.core.errors import NoCandidateError

__all__ = ["dispatch"]


async def _wait_for_candidates(
    registry: Any, model: str, timeout: float = 15.0, platform: str = ""
) -> List[Candidate]:
    """等待候选项就绪。"""
    deadline = time.monotonic() + timeout
    cfg = get_config()
    while time.monotonic() < deadline:
        cands = await registry.get_candidates(model)
        if platform:
            cands = [c for c in cands if c.platform == platform]
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
) -> tuple[int, List[Candidate]]:
    """根据网关配置选择并发数与候选项子集。"""
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
    """核心分发：选择候选项并执行单发或竞速请求。"""
    from src.core.errors import GatewayAbortedError
    from src.core.server.plugins.hook_registry import get_hook_registry

    hook_ctx = {
        "registry": registry,
        "messages": messages,
        "model": model,
        "stream": stream,
        "platform": platform,
        "tools": tools,
    }
    before = await get_hook_registry().invoke("gateway.request.before", hook_ctx)
    if before.aborted:
        raise GatewayAbortedError(before.abort_reason or "gateway.request.before aborted")
    messages = list(before.context.get("messages", messages))
    model = str(before.context.get("model", model))
    platform = str(before.context.get("platform", platform))

    final_msgs = fold_system_into_user(messages, tools)

    cands = await _wait_for_candidates(registry, model, timeout=15.0, platform=platform)
    if not cands:
        raise NoCandidateError("无候选项: {}".format(model))

    n, sel = await _select_dispatch_candidates(registry, cands, stream)

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

    await get_hook_registry().invoke(
        "gateway.request.after",
        {
            "registry": registry,
            "model": model,
            "stream": stream,
            "platform": platform,
            "candidate_count": len(sel),
        },
    )
