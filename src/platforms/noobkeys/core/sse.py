from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Union


def parse_sse_line(data_str: str) -> Optional[Union[str, Dict[str, Any]]]:
    """解析 OpenAI 兼容 SSE data 字段内容。

    支持：
    - ``delta.content`` → 文本增量（str）
    - ``delta.reasoning`` / ``delta.reasoning_content`` → ``{"thinking": ...}``
    - ``usage`` → ``{"usage": {...}}``

    Args:
        data_str: ``data:`` 前缀之后的字符串，已去除前缀和两端空白。

    Returns:
        ``str``（文本片段）、``dict``（thinking / usage）或 ``None``（跳过）。
    """
    if not data_str or data_str == "[DONE]":
        return None

    try:
        obj = json.loads(data_str)
    except (json.JSONDecodeError, ValueError):
        return None

    choices = obj.get("choices") or []
    choice = choices[0] if choices else {}
    delta = choice.get("delta", {}) or {}

    reasoning = delta.get("reasoning_content") or delta.get("reasoning")
    if reasoning:
        return {"thinking": reasoning}

    content = delta.get("content", "")
    if content:
        return content

    usage = obj.get("usage")
    if usage and isinstance(usage, dict):
        return {
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
            }
        }

    return None
