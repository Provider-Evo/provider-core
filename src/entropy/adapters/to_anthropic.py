from __future__ import annotations

from typing import Any, Dict, List

from src.entropy.core.types import TurnResponse


def to_anthropic_message_response(
    turn: TurnResponse,
    *,
    model: str,
    message_id: str,
    input_tokens: int,
    output_tokens: int,
) -> Dict[str, Any]:
    """TurnResponse → Anthropic message 非流式响应。"""
    blocks: List[Dict[str, Any]] = []
    for block in turn.output:
        if block.type == "thinking" and block.thinking:
            blocks.append({"type": "thinking", "thinking": block.thinking})
        elif block.type == "text" and block.text:
            blocks.append({"type": "text", "text": block.text})
        elif block.type == "tool_call" and block.tool_call:
            from src.routes.anthropic.convert import _openai_tc_to_anth

            blocks.append(_openai_tc_to_anth(block.tool_call))
    return {
        "id": message_id,
        "type": "message",
        "role": "assistant",
        "content": blocks,
        "model": model,
        "stop_reason": "tool_use" if turn.tool_calls else "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
    }
