from __future__ import annotations

import json
from typing import Any, Dict, Optional, Union


def parse_sse_line(data_str: str) -> Optional[Union[str, Dict[str, Any]]]:
    """Parse a single SSE data line.

    Args:
        data_str: Raw SSE data string.

    Returns:
        Content string, dict with thinking/usage, or None.

    Raises:
        ValueError: When SSE data contains an error field.

    Examples:
        >>> parse_sse_line("[DONE]")
        >>> parse_sse_line("")
        >>> parse_sse_line('{"choices":[{"delta":{"content":"hi"}}]}')
        'hi'
    """
    if not data_str or data_str == "[DONE]":
        return None
    try:
        obj = json.loads(data_str)
    except (json.JSONDecodeError, ValueError):
        return None
    if "error" in obj:
        raise ValueError("SSE error: {}".format(obj["error"]))
    choices = obj.get("choices", [])
    if not choices:
        if obj.get("usage"):
            return {"usage": obj["usage"]}
        return None
    delta = choices[0].get("delta", {})
    content = delta.get("content")
    if content:
        return content
    reasoning = delta.get("reasoning_content") or delta.get("thinking")
    if reasoning:
        return {"thinking": reasoning}
    if obj.get("usage"):
        return {"usage": obj["usage"]}
    return None
