"""Chutes 工具函数"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Union

BASE_URL: str = "https://llm.chutes.ai"
CHAT_PATH: str = "/v1/chat/completions"

# 流式请求最大 token 数
MAX_TOKENS_STREAMING: int = 65536
# 非流式请求最大 token 数
MAX_TOKENS_NON_STREAMING: int = 4096


def build_headers(api_key: str) -> Dict[str, str]:
    """构建 Chutes 接口请求头。

    Args:
        api_key: Chutes API Key。

    Returns:
        完整请求头字典。
    """
    return {
        "Authorization": "Bearer {}".format(api_key),
        "Content-Type": "application/json",
    }


def build_payload(
    messages: List[Dict[str, Any]],
    model: str,
    stream: bool = True,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    stop: Optional[Any] = None,
) -> Dict[str, Any]:
    """构建聊天请求体。

    Args:
        messages: 消息列表。
        model: 模型名称。
        stream: 是否启用流式响应。
        max_tokens: 最大生成 token 数，None 时按流式/非流式默认值。
        temperature: 采样温度。
        top_p: 核采样概率。
        stop: 停止词。

    Returns:
        请求体字典。
    """
    if max_tokens is None:
        max_tokens = MAX_TOKENS_STREAMING if stream else MAX_TOKENS_NON_STREAMING

    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "max_tokens": max_tokens,
    }
    if temperature is not None:
        payload["temperature"] = temperature
    if top_p is not None:
        payload["top_p"] = top_p
    if stop:
        payload["stop"] = stop
    return payload


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
