from __future__ import annotations

from typing import Any, Dict, List, Optional, Union


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
