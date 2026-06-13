"""Cursor 平台 SSE 解析。"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, Union


def parse_sse_line(data_str: str) -> Optional[Union[str, Dict[str, Any]]]:
    """解析 SSE data 字段内容。

    从 cursor-client.ts SSE 解析逻辑移植。
    支持 text-delta / finish 两种事件类型。

    Args:
        data_str: data: 前缀之后的字符串，已去除前缀和空白。

    Returns:
        str（文本片段）、dict（usage）或 None（跳过）。

    Raises:
        ValueError: 当 SSE 包含 error 字段时。
    """
    if not data_str or data_str == "[DONE]":
        return None

    try:
        obj = json.loads(data_str)
    except (json.JSONDecodeError, ValueError):
        return None

    if "error" in obj:
        raise ValueError("Cursor SSE error: {}".format(obj["error"]))

    event_type = obj.get("type", "")

    if event_type == "text-delta":
        delta = obj.get("delta", "")
        return delta if delta else None

    if event_type == "finish":
        meta = obj.get("messageMetadata")
        if meta and meta.get("usage"):
            usage = meta["usage"]
            return {
                "usage": {
                    "input_tokens": usage.get("inputTokens"),
                    "output_tokens": usage.get("outputTokens"),
                    "total_tokens": usage.get("totalTokens"),
                }
            }
        return None

    return None
