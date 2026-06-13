"""Cursor 平台请求体构造。"""

from __future__ import annotations

from typing import Any, Dict, List

from .conversation import derive_conversation_id


def build_payload(
    cursor_messages: List[Dict[str, Any]],
    model: str = "google/gemini-3-flash",
    **kw: Any,
) -> Dict[str, Any]:
    """构建 Cursor /api/chat 请求体。

    Args:
        cursor_messages: Cursor 格式消息列表。
        model: 模型名。
        **kw: 其他参数（忽略）。

    Returns:
        请求体字典。
    """
    conv_id = derive_conversation_id(cursor_messages)
    return {
        "model": model,
        "id": conv_id,
        "messages": cursor_messages,
        "trigger": "submit-message",
    }
