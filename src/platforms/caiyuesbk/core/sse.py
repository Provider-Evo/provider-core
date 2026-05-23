from __future__ import annotations

import json
from typing import Any, Dict, Optional, Union


def parse_sse_line(data_str: str) -> Optional[Union[str, Dict[str, Any]]]:
    """解析单行 SSE data 字段内容。

    Args:
        data_str: 去掉 "data: " 前缀后的原始字符串。

    Returns:
        文本增量（str）、usage 字典（dict）或 None（解析失败/无内容）。
    """
    try:
        chunk: Dict[str, Any] = json.loads(data_str)
    except (json.JSONDecodeError, ValueError):
        return None

    choices = chunk.get("choices")
    if choices:
        delta = choices[0].get("delta", {})
        content = delta.get("content")
        if content:
            return content

    usage = chunk.get("usage")
    if usage:
        return {"usage": usage}

    return None
