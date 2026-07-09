from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_payload(
    messages: List[Dict[str, Any]],
    model: str,
    *,
    stream: bool = False,
    temperature: Optional[float] = None,
    **kw: Any,
) -> Dict[str, Any]:
    """构建聊天补全请求体。

    Args:
        messages: 消息列表。
        model: 模型名。
        stream: 是否流式。
        temperature: 温度参数，可选。
        **kw: 额外参数（如 top_p 等）。

    Returns:
        请求体字典。
    """
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": stream,
    }
    if temperature is not None:
        payload["temperature"] = temperature
    for k, v in kw.items():
        if v is not None:
            payload[k] = v
    return payload
