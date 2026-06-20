from __future__ import annotations

import json
from typing import Any, Dict, Optional, Union


def parse_sse_line(data_str: str) -> Optional[Union[str, Dict[str, Any]]]:
    """Parse SSE data field content.

    Args:
        data_str: String after the ``data:`` prefix, with leading
            whitespace already stripped.

    Returns:
        str (text chunk), dict (thinking/tool_calls/usage), or None (skip).
    """
    if not data_str or data_str == "[DONE]":
        return None

    try:
        obj = json.loads(data_str)
    except (json.JSONDecodeError, ValueError):
        return None

    choice = (obj.get("choices") or [{}])[0]
    delta = choice.get("delta", {})

    # reasoning field for thinking content
    reasoning = delta.get("reasoning")
    if reasoning:
        return {"thinking": reasoning}

    # Also check reasoning_content for compatibility
    reasoning_content = delta.get("reasoning_content")
    if reasoning_content:
        return {"thinking": reasoning_content}

    content = delta.get("content", "")
    if content:
        return content

    tc = delta.get("tool_calls")
    if tc:
        return {"tool_calls": tc}

    usage = obj.get("usage")
    if usage and isinstance(usage, dict):
        return {"usage": {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
        }}

    return None
