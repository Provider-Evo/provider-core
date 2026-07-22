from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from src.entropy.core.blocks import build_turn_response
from src.entropy.core.types import TurnRequest, TurnResponse
from src.routes.shared.thinking import ThinkingConfig, thinking_to_dispatch_kwargs


async def execute_turn(
    turn: TurnRequest,
    registry: Any,
) -> AsyncGenerator[Union[str, Dict[str, Any], TurnResponse], None]:
    """Entropy 内核：统一调用 gateway.dispatch。"""
    from src.core import gateway

    thinking_cfg = turn.thinking or ThinkingConfig()
    dispatch_kw = thinking_to_dispatch_kwargs(thinking_cfg)
    async for chunk in gateway.dispatch(
        registry=registry,
        messages=turn.input,
        model=turn.model,
        stream=turn.stream,
        tools=turn.tools,
        search=turn.search,
        temperature=turn.temperature,
        top_p=turn.top_p,
        max_tokens=turn.max_output_tokens,
        stop=turn.stop,
        upload_files=turn.upload_files,
        protocol_id=turn.protocol_id,
        tool_choice=turn.tool_choice,
        platform=turn.platform,
        **dispatch_kw,
    ):
        yield chunk


async def collect_turn(
    turn: TurnRequest,
    registry: Any,
) -> TurnResponse:
    """非流式收集完整 TurnResponse。"""
    text_parts: List[str] = []
    thinking_parts: List[str] = []
    tool_calls: List[Dict[str, Any]] = []
    usage: Optional[Dict[str, Any]] = None
    platform_id = ""

    async for ch in execute_turn(turn, registry):
        if isinstance(ch, TurnResponse):
            return ch
        if isinstance(ch, str):
            text_parts.append(ch)
            continue
        if not isinstance(ch, dict):
            continue
        if "_meta" in ch:
            platform_id = ch["_meta"].get("platform", "")
        elif "thinking" in ch:
            thinking_parts.append(ch["thinking"])
        elif "tool_calls" in ch:
            tool_calls = ch["tool_calls"]
        elif "usage" in ch:
            usage = ch["usage"]

    return build_turn_response(
        text_parts=text_parts,
        thinking_parts=thinking_parts,
        tool_calls=tool_calls,
        usage=usage,
        platform_id=platform_id,
        model=turn.model,
    )
