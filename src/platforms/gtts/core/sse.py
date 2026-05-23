from __future__ import annotations

"""gTTS SSE 解析（纯函数，无状态）。"""

import json
from typing import Any, Dict, Optional, Union


def parse_sse_line(data_str: str) -> Optional[Union[str, Dict[str, Any]]]:
    """解析 SSE 行（占位实现，gTTS 不使用 SSE）。

    Args:
        data_str: SSE 数据行字符串。

    Returns:
        解析结果（文本字符串或用例字典），无有效数据时返回 None。
    """
    if not data_str or data_str == "[DONE]":
        return None
    try:
        obj = json.loads(data_str)
    except (json.JSONDecodeError, ValueError):
        return None
    choices = obj.get("choices", [])
    if choices:
        delta = choices[0].get("delta", {})
        if delta.get("content"):
            return delta["content"]
    if obj.get("usage"):
        return {"usage": obj["usage"]}
    return None
