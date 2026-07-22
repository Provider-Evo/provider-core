from __future__ import annotations

from typing import Any, Dict, List

from src.entropy.core.types import TurnResponse


def to_entropy_turn_response(turn: TurnResponse) -> Dict[str, Any]:
    """TurnResponse → Entropy /v1/turns 响应体。"""
    output: List[Dict[str, Any]] = []
    for block in turn.output:
        if block.type == "text" and block.text:
            output.append({"type": "text", "text": block.text})
        elif block.type == "thinking" and block.thinking:
            output.append({"type": "thinking", "thinking": block.thinking})
        elif block.type == "tool_call" and block.tool_call:
            output.append({"type": "tool_call", "tool_call": block.tool_call})
        elif block.type == "tool_result" and block.tool_result:
            output.append({"type": "tool_result", "tool_result": block.tool_result})
    payload: Dict[str, Any] = {
        "object": "turn",
        "model": turn.model,
        "output": output,
    }
    if turn.usage:
        payload["usage"] = turn.usage
    if turn.platform_id:
        payload["platform"] = turn.platform_id
    return payload
