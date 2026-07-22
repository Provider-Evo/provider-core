from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.entropy.core.types import TurnResponse


def to_openai_chat_response(
    turn: TurnResponse,
    *,
    model: str,
    completion_id: str,
    created: int,
) -> Dict[str, Any]:
    """TurnResponse → OpenAI chat.completion 非流式响应。"""
    message: Dict[str, Any] = {"role": "assistant", "content": turn.raw_text or None}
    thinking = next((b.thinking for b in turn.output if b.type == "thinking"), None)
    if thinking:
        message["reasoning_content"] = thinking
    if turn.tool_calls:
        message["tool_calls"] = turn.tool_calls
        message["content"] = turn.raw_text or None
    choice: Dict[str, Any] = {
        "index": 0,
        "message": message,
        "finish_reason": "tool_calls" if turn.tool_calls else "stop",
    }
    payload: Dict[str, Any] = {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": model,
        "choices": [choice],
    }
    if turn.usage:
        payload["usage"] = turn.usage
    return payload
