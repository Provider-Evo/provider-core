"""caiyuesbk 工具函数——纯函数，无副作用，无 I/O"""

from __future__ import annotations

import json
import ssl
from typing import Any, Dict, List, Optional, Union


BASE_URL: str = "https://caiyuesbk.top:16188"
CHAT_PATH: str = "/v1/chat/completions"


def make_ssl_ctx() -> ssl.SSLContext:
    """创建禁用证书验证的 SSL 上下文。"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def build_headers(api_key: str) -> Dict[str, str]:
    """构建 HTTP 请求头。

    Args:
        api_key: caiyuesbk 平台 API Key。

    Returns:
        包含鉴权信息和内容类型的请求头字典。
    """
    return {
        "Authorization": "Bearer {}".format(api_key),
        "Content-Type": "application/json",
    }


def build_payload(
    messages: List[Dict[str, Any]],
    model: str,
    stream: bool,
    *,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    max_tokens: Optional[int] = None,
    stop: Optional[Union[str, List[str]]] = None,
) -> Dict[str, Any]:
    """构建聊天补全请求体。

    Args:
        messages: 对话消息列表。
        model: 模型名称。
        stream: 是否启用流式响应。
        temperature: 采样温度，可选。
        top_p: 核采样概率，可选。
        max_tokens: 最大生成 token 数，可选。
        stop: 停止序列，可选。

    Returns:
        符合 OpenAI 接口规范的请求体字典。
    """
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": stream,
    }
    if temperature is not None:
        payload["temperature"] = temperature
    if top_p is not None:
        payload["top_p"] = top_p
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if stop is not None:
        payload["stop"] = stop
    return payload


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
