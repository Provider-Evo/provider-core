"""CodeBuddy 工具函数"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Union

BASE_URL: str = "https://www.codebuddy.ai"
CHAT_PATH: str = "/v2/chat/completions"
IDE_VERSION: str = "1.0.7"


def build_headers(
    token: str = "",
    user_id: str = "",
    conversation_id: str = "",
    conversation_request_id: str = "",
    conversation_message_id: str = "",
    request_id: str = "",
) -> Dict[str, str]:
    """构建 CodeBuddy 接口请求头（纯函数，不生成随机值）。

    Args:
        token: Bearer 鉴权令牌。
        user_id: 用户唯一标识。
        conversation_id: 会话 ID。
        conversation_request_id: 会话请求 ID。
        conversation_message_id: 会话消息 ID。
        request_id: 请求 ID。

    Returns:
        完整请求头字典。
    """
    return {
        "Host": "www.codebuddy.ai",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "x-stainless-arch": "x64",
        "x-stainless-lang": "js",
        "x-stainless-os": "Windows",
        "x-stainless-package-version": "5.10.1",
        "x-stainless-retry-count": "0",
        "x-stainless-runtime": "node",
        "x-stainless-runtime-version": "v22.13.1",
        "X-Conversation-ID": conversation_id,
        "X-Conversation-Request-ID": conversation_request_id,
        "X-Conversation-Message-ID": conversation_message_id,
        "X-Request-ID": request_id,
        "X-Agent-Intent": "craft",
        "X-IDE-Type": "CLI",
        "X-IDE-Name": "CLI",
        "X-IDE-Version": IDE_VERSION,
        "Authorization": "Bearer {}".format(token),
        "X-Domain": "www.codebuddy.ai",
        "User-Agent": "CLI/{0} CodeBuddy/{0}".format(IDE_VERSION),
        "X-Product": "SaaS",
        "X-User-Id": user_id,
    }


def build_payload(
    messages: List[Dict[str, Any]],
    model: str = "auto-chat",
    stream: bool = True,
    **kw: Any,
) -> Dict[str, Any]:
    """构建聊天请求体。

    Args:
        messages: 消息列表，每条包含 role 和 content。
        model: 模型名称。
        stream: 是否启用流式响应。
        **kw: 额外参数（预留扩展）。

    Returns:
        请求体字典。
    """
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": stream,
    }
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
