"""N1N 请求体构造。"""

from __future__ import annotations

from typing import Any, Dict, List


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
