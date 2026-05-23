# src/platforms/openrouter/util.py
"""OpenRouter工具函数"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Union

BASE_URL: str = "https://openrouter.ai/api/v1"
CHAT_PATH: str = "/chat/completions"
EMBED_PATH: str = "/embeddings"
MODELS_PATH: str = "/models"

DEFAULT_HEADERS: Dict[str, str] = {
    "Content-Type": "application/json",
    "HTTP-Referer": "https://provider-v2.local",
    "X-Title": "Provider-V2",
}


def build_headers(api_key: str = "") -> Dict[str, str]:
    """构建请求头。

    Args:
        api_key: OpenRouter API Key。

    Returns:
        请求头字典。
    """
    headers: Dict[str, str] = dict(DEFAULT_HEADERS)
    if api_key:
        headers["Authorization"] = "Bearer {}".format(api_key)
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
        **kw: 额外参数（temperature, top_p, max_tokens, stop）。

    Returns:
        请求体字典。
    """
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": stream,
    }
    if kw.get("temperature") is not None:
        payload["temperature"] = kw["temperature"]
    if kw.get("top_p") is not None:
        payload["top_p"] = kw["top_p"]
    if kw.get("max_tokens") is not None:
        payload["max_tokens"] = kw["max_tokens"]
    if kw.get("stop"):
        payload["stop"] = kw["stop"]
    return payload


def parse_sse_line(data_str: str) -> Optional[Union[str, Dict[str, Any]]]:
    """解析SSE data字段内容。

    Args:
        data_str: data: 前缀之后的字符串，已去除前缀和空白。

    Returns:
        str（文本片段）、dict（thinking/tool_calls/usage）或None（跳过）。
    """
    if not data_str or data_str == "[DONE]":
        return None

    try:
        obj = json.loads(data_str)
    except (json.JSONDecodeError, ValueError):
        return None

    choice = (obj.get("choices") or [{}])[0]
    delta = choice.get("delta", {})

    reasoning = delta.get("reasoning_content")
    if reasoning:
        return {"thinking": reasoning}

    content = delta.get("content", "")
    if content:
        return content

    tc = delta.get("tool_calls")
    if tc:
        return {"tool_calls_delta": tc}

    usage = obj.get("usage")
    if usage and isinstance(usage, dict):
        return {"usage": {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
        }}

    return None
