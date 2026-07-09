"""Noobkeys SSE 解析（无状态层）。

在 OpenAI 兼容格式基础上额外支持 delta.reasoning 字段。
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Union

from src.platforms.sse_common import load_sse_json

__all__ = ["parse_sse_line"]


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
    obj = load_sse_json(data_str)
    if obj is None:
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
        return {"usage": usage}

    return None
