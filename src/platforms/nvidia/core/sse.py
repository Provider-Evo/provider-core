from __future__ import annotations

"""Nvidia SSE 行解析（无状态层）。"""

import json
from typing import Any, Dict, Optional, Union


def parse_sse_line(data_str: str) -> Optional[Union[str, Dict[str, Any]]]:
    """解析SSE data字段内容。

    Args:
        data_str: data: 前缀之后的字符串，已去除前缀和空白。

    Returns:
        str（文本片段）、dict（thinking/usage）或None（跳过）。

    Examples:
        >>> parse_sse_line("[DONE]") is None
        True
        >>> parse_sse_line("") is None
        True
        >>> parse_sse_line('{"choices":[{"delta":{"content":"hi"}}]}')
        'hi'
        >>> parse_sse_line('{"choices":[{"delta":{"reasoning_content":"think"}}]}')
        {'thinking': 'think'}
    """
    if not data_str or data_str == "[DONE]":
        return None

    try:
        obj = json.loads(data_str)
    except (json.JSONDecodeError, ValueError):
        return None

    choice = (obj.get("choices") or [{}])[0]
    delta = choice.get("delta", {})

    reasoning = delta.get("reasoning_content")
    if reasoning:
        return {"thinking": reasoning}

    content = delta.get("content", "")
    if content:
        return content

    usage = obj.get("usage")
    if usage and isinstance(usage, dict):
        return {"usage": {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
        }}

    return None
