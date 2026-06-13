from __future__ import annotations

"""gTTS 请求体构造。"""

from typing import Any, Dict, List

from .constants import DEFAULT_MODEL


def build_payload(
    messages: List[Dict[str, Any]],
    model: str = "",
    stream: bool = True,
    **kw: Any,
) -> Dict[str, Any]:
    """构建聊天请求体占位。

    Args:
        messages: 消息列表。
        model: 模型名。
        stream: 是否流式。
        **kw: 额外参数。

    Returns:
        请求体字典。
    """
    payload: Dict[str, Any] = {
        "model": model or DEFAULT_MODEL,
        "messages": messages,
        "stream": stream,
    }
    payload.update(kw)
    return payload
