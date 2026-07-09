"""Cerebras 请求体构造工具。"""

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
