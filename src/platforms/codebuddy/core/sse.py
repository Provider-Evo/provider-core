"""CodeBuddy SSE 单行解析（无状态）。

提供纯函数解析 SSE data 字段内容，不含任何 I/O 或累积状态。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Union


def parse_sse_line(data_str: str) -> Optional[Union[str, Dict[str, Any]]]:
    """解析 SSE data 字段内容。

    接收去除 ``data:`` 前缀后的字符串，解析 JSON 并按 yield 协议
    返回文本片段、thinking 字典、usage 字典或 None。

    Args:
        data_str: ``data:`` 前缀之后的字符串，已去除前缀和首尾空白。

    Returns:
        文本片段（str）、元数据字典（dict）或 None（跳过该事件）。

    Raises:
        ValueError: SSE 事件包含 error 字段时抛出。
    """
    if not data_str or data_str == "[DONE]":
        return None

    try:
        obj = json.loads(data_str)
    except (json.JSONDecodeError, ValueError):
        return None

    if "error" in obj:
        raise ValueError("SSE 错误: {}".format(obj["error"]))

    choices = obj.get("choices", [])
    if not choices:
        usage = obj.get("usage")
        if usage:
            return {"usage": usage}
        return None

    choice = choices[0]
    delta = choice.get("delta", {})

    reasoning_content = delta.get("reasoning_content")
    if reasoning_content:
        return {"thinking": reasoning_content}

    content = delta.get("content")
    if content:
        return content

    usage = obj.get("usage")
    if usage:
        return {"usage": usage}

    return None
