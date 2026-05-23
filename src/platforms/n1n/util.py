# src/platforms/n1n/util.py
"""N1N工具函数"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Union

BASE_URL: str = "https://api.n1n.ai"
CHAT_PATH: str = "/pg/chat/completions"
MODELS_PATH: str = "/api/user/models?group=default"


def build_headers(token: str = "") -> Dict[str, str]:
    """构建请求头。

    Args:
        token: API Key，用于Authorization头。

    Returns:
        请求头字典。
    """
    headers: Dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN",
        "Cache-Control": "no-store",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/148.0.0.0 Safari/537.36"
        ),
    }
    if token:
        headers["Authorization"] = "Bearer {}".format(token)
    return headers


def build_payload(
    messages: List[Dict[str, Any]],
    model: str = "",
    stream: bool = True,
    **kw: Any,
) -> Dict[str, Any]:
    """构建聊天请求体。

    Args:
        messages: 消息列表。
        model: 模型名。
        stream: 是否流式。
        **kw: 额外参数。

    Returns:
        请求体字典。
    """
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "temperature": 1,
        "top_p": 1,
        "frequency_penalty": 0,
        "presence_penalty": 0,
        "group": "default",
    }
    for k, v in kw.items():
        payload[k] = v
    return payload


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
