from __future__ import annotations

"""ChatMoe 请求体构造。"""

import uuid
from typing import Any, Dict, List


def build_payload(
    messages: List[Dict[str, Any]],
    model: str,
    *,
    stream: bool = True,
    thinking: bool = False,
    search: bool = False,
) -> Dict[str, Any]:
    """构建聊天请求体。

    Args:
        messages: 消息列表。
        model: 模型名称（ChatMoe 内部固定，此参数保留兼容性）。
        stream: 是否流式输出。
        thinking: 是否启用深度思考。
        search: 是否启用联网搜索。

    Returns:
        请求体字典。
    """
    return {
        "stream": stream,
        "user_id": str(uuid.uuid4()),
        "tools": [
            {
                "type": "web_search",
                "web_search": {
                    "search_engine": "search_std",
                    "enable": search,
                    "search_intent": True,
                },
            }
        ],
        "thinking": {"type": "enabled" if thinking else "disabled"},
        "messages": [
            {
                "role": m.get("role", "user"),
                "content": m.get("content", ""),
            }
            for m in messages
        ],
        "type": "text",
        "style": "default",
        "provider": "chatmoe_z",
    }
