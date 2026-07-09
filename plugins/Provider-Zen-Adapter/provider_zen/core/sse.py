"""Zen SSE 解析（无状态层）。

在 OpenAI 兼容格式基础上额外支持 reasoning 和 tool_calls 字段。
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Union

from provider_sdk.extensions.platform.sse_common import load_sse_json

__all__ = ["parse_sse_line"]


def parse_sse_line(data_str: str) -> Optional[Union[str, Dict[str, Any]]]:
    """解析 SSE data 字段内容（OpenAI 兼容 + reasoning + tool_calls）。

    Args:
        data_str: data: 前缀之后的字符串，已去除前缀和空白。

    Returns:
        str（文本片段）、dict（thinking/tool_calls/usage）或 None（跳过）。
    """
    obj = load_sse_json(data_str)
    if obj is None:
        return None

    choice = (obj.get("choices") or [{}])[0]
    delta = choice.get("delta", {})

    reasoning = delta.get("reasoning") or delta.get("reasoning_content")
    if reasoning:
        return {"thinking": reasoning}

    content = delta.get("content", "")
    if content:
        return content

    tc = delta.get("tool_calls")
    if tc:
        return {"tool_calls": tc}

    usage = obj.get("usage")
    if usage and isinstance(usage, dict):
        return {"usage": usage}

    return None
