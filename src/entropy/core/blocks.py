from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.entropy.core.types import OutputBlock, TurnResponse


def build_turn_response(
    *,
    text_parts: List[str],
    thinking_parts: List[str],
    tool_calls: List[Dict[str, Any]],
    usage: Optional[Dict[str, Any]],
    platform_id: str,
    model: str,
) -> TurnResponse:
    output: List[OutputBlock] = []
    if thinking_parts:
        output.append(OutputBlock(type="thinking", thinking="".join(thinking_parts)))
    text = "".join(text_parts)
    if text:
        output.append(OutputBlock(type="text", text=text))
    for tc in tool_calls:
        output.append(OutputBlock(type="tool_call", tool_call=tc))
    return TurnResponse(
        output=output,
        usage=usage,
        platform_id=platform_id,
        model=model,
        raw_text=text,
        tool_calls=tool_calls,
    )
