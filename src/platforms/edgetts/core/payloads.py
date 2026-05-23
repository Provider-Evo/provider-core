"""Edge TTS 请求体构造（占位，TTS 平台主要用于语音合成）。"""

from __future__ import annotations

from typing import Any, Dict, List


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
        **kw: 其他字段。

    Returns:
        请求体字典。
    """
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": stream,
    }
    payload.update(kw)
    return payload
