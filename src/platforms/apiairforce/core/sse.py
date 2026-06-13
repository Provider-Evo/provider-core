from __future__ import annotations

import json
from typing import Any, Dict, Optional, Union


def parse_sse_line(data_str: str) -> Optional[Union[str, Dict[str, Any]]]:
    """解析 SSE data 行，返回文本增量或 usage。

    Args:
        data_str: SSE data 字段内容（不含 "data: " 前缀）。

    Returns:
        文本增量字符串、usage 字典，或 None（无法解析/终止块）。

    >>> parse_sse_line('{"choices":[{"delta":{"content":"hello"}}]}')
    'hello'
    >>> parse_sse_line('{"choices":[],"usage":{"prompt_tokens":10}}')
    {'usage': {'prompt_tokens': 10}}
    >>> parse_sse_line('[DONE]')
    """
    try:
        obj = json.loads(data_str)
    except json.JSONDecodeError:
        return None

    # 终止块
    if obj.get("choices") == [] and obj.get("usage"):
        return {"usage": obj["usage"]}

    choices = obj.get("choices") or []
    if not choices:
        return None

    delta = choices[0].get("delta") or {}
    content = delta.get("content")
    if content:
        return content
    return None
