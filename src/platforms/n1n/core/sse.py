"""N1N SSE 解析（无状态层）。"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, Union


def parse_sse_line(data_str: str) -> Optional[Union[str, Dict[str, Any]]]:
    """解析SSE data字段内容。

    Args:
        data_str: data: 前缀之后的字符串，已去除前缀和空白。

    Returns:
        str（文本片段）、dict（thinking/usage）或None（跳过）。
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
        usage = obj.get("usage")
        if usage and isinstance(usage, dict) and len(usage) > 0:
            return {"usage": usage}
        return None

    choice = choices[0]
    delta = choice.get("delta", {})

    rc = delta.get("reasoning_content")
    if rc:
        return {"thinking": rc}

    content = delta.get("content")
    if content:
        return content

    usage = obj.get("usage")
    if usage and isinstance(usage, dict) and len(usage) > 0:
        return {"usage": usage}

    return None
