from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional

from src.core.dispatch.cand import (
    Candidate,
    filter_candidates_by_capability,
    filter_candidates_by_context,
    messages_require_capability,
)
from src.core.dispatch.circuit import get_platform_circuit_breaker
from src.core.utils.errors import NoCandidateError
from src.foundation.config import get_config

__all__ = ["dispatch"]


def _estimate_prompt_tokens(messages: List[Dict]) -> int:
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        total += _estimate_message_content_tokens(content)
    return total + 64


def _tokens_for_content_part(part: Dict) -> int:
    part_type = part.get("type", "")
    if part_type == "text":
        return max(1, len(str(part.get("text", ""))) // 4)
    if part_type in ("image_url", "input_audio"):
        return 256
    return 0


def _estimate_message_content_tokens(content: Any) -> int:
    """辅助函数：计算单条消息内容的 token 估算值。"""
    if isinstance(content, str):
        return max(1, len(content) // 4)
    if not isinstance(content, list):
        return 0
    token_count = 0
    for part in content:
        if isinstance(part, dict):
            token_count += _tokens_for_content_part(part)
    return token_count


async def _wait_for_candidates(
    registry: Any,
    model: str,
    timeout: float = 15.0,
    platform: str = "",
    cfg: Any = None,
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
        await registry.ensure_candidates(model, max(cfg.gateway.concurrent_count, 3))
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
    cands = await _wait_for_candidates(
        registry, model, timeout=15.0, platform=platform, cfg=cfg
    )
    if not cands:
        raise NoCandidateError("无候选项: {}".format(model))

    cands = await _filter_dispatch_candidates(cands, messages, model, max_tokens)

    _n, sel = await _select_dispatch_candidates(registry, cands, stream, cfg=cfg)
    return sel


async def _run_gateway_before_hook(
    registry: Any,
    messages: List[Dict],
    model: str,
    stream: bool,
    platform: str,
    tools: Optional[List[Dict]],
) -> tuple[List[Dict], str, str]:
    """执行 gateway.request.before hook，返回可能被 hook 改写后的 messages/model/platform。"""
    from src.core.server.http.request_context import get_api_token
    from src.core.server.plugins.hook_reg import get_hook_registry
    from src.core.utils.errors import GatewayAbortedError

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
        raise GatewayAbortedError(
            before.abort_reason or "gateway.request.before aborted"
        )
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


from src.core.dispatch.engine.support.gateway_dispatch import dispatch  # noqa: E402
