"""CodeBuddy HTTP 请求体构建工具。

封装 CodeBuddy 聊天补全接口的载荷组装。
"""

from __future__ import annotations

from typing import Any, Dict, List


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
