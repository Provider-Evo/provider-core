"""Edge TTS SSE 行解析（占位，TTS 平台不使用 SSE）。"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, Union


def parse_sse_line(data_str: str) -> Optional[Union[str, Dict[str, Any]]]:
    """解析 SSE 行。

    Args:
        data_str: data 段字符串。

    Returns:
        文本片段、字典或 None。
    """
    if not data_str or data_str == "[DONE]":
        return None
    try:
        obj = json.loads(data_str)
    except (json.JSONDecodeError, ValueError):
        return None
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
