"""Cerebras 工具函数"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_params(
    messages: List[Dict[str, Any]],
    model: str,
    stream: bool,
    temperature: float = 0.7,
    top_p: float = 0.8,
    max_tokens: Optional[int] = None,
    frequency_penalty: Optional[float] = None,
    presence_penalty: Optional[float] = None,
    stop: Optional[Any] = None,
    user: Optional[str] = None,
) -> Dict[str, Any]:
    """构建 Cerebras SDK 请求参数。

    Args:
        messages: 对话消息列表。
        model: 模型名称。
        stream: 是否流式输出。
        temperature: 采样温度。
        top_p: nucleus 采样概率。
        max_tokens: 最大输出 token 数，None 则不传递。
        frequency_penalty: 频率惩罚，None 则不传递。
        presence_penalty: 存在惩罚，None 则不传递。
        stop: 停止序列，None 则不传递。
        user: 用户标识，None 则不传递。

    Returns:
        SDK create() 方法所需的参数字典。
    """
    params: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "top_p": top_p,
        "stream": stream,
    }
    if max_tokens is not None:
        params["max_completion_tokens"] = max_tokens
    if frequency_penalty is not None:
        params["frequency_penalty"] = frequency_penalty
    if presence_penalty is not None:
        params["presence_penalty"] = presence_penalty
    if stop is not None:
        params["stop"] = stop
    if user is not None:
        params["user"] = user
    return params


def extract_usage(usage_obj: Any) -> Dict[str, int]:
    """从 SDK 响应的 usage 对象提取 token 用量。

    Args:
        usage_obj: Cerebras SDK 返回的 usage 对象（含 prompt_tokens 等属性）。

    Returns:
        标准 usage 字典，包含 prompt_tokens、completion_tokens、total_tokens。
    """
    return {
        "prompt_tokens": int(getattr(usage_obj, "prompt_tokens", 0)),
        "completion_tokens": int(getattr(usage_obj, "completion_tokens", 0)),
        "total_tokens": int(getattr(usage_obj, "total_tokens", 0)),
    }


def extract_delta_content(chunk: Any) -> Optional[str]:
    """从流式 chunk 中提取增量文本内容。

    Args:
        chunk: Cerebras SDK 流式响应的单个 chunk 对象。

    Returns:
        增量文本字符串，若无内容则返回 None。
    """
    if not chunk.choices:
        return None
    delta = chunk.choices[0].delta
    if delta is None:
        return None
    content = getattr(delta, "content", None)
    if not content:
        return None
    return content


def extract_nonstream_content(resp: Any) -> Optional[str]:
    """从非流式响应中提取完整文本内容。

    Args:
        resp: Cerebras SDK 非流式响应对象。

    Returns:
        完整文本字符串，若无内容则返回 None。
    """
    if not resp.choices:
        return None
    message = resp.choices[0].message
    if message is None:
        return None
    content = getattr(message, "content", None)
    if not content:
        return None
    return content
