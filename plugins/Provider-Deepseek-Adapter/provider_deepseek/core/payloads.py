from __future__ import annotations

"""DeepSeek 请求体构造。"""

from typing import Any, Dict, Optional

from .client import make_stream_id
from .constants import MODEL_TYPE_MAP, MODEL_VISION


def build_payload(
    session_id: str,
    prompt: str,
    model: str,
    *,
    thinking: bool = False,
    search: bool = False,
    stream_id: Optional[str] = None,
) -> Dict[str, Any]:
    """构建 DeepSeek ``/api/v0/chat/completion`` 请求体。

    Args:
        session_id: 会话 ID。
        prompt: 提示文本。
        model: 模型名。
        thinking: 是否启用思考模式。
        search: 是否启用联网搜索。
        stream_id: 客户端流 ID（可选，自动生成）。

    Returns:
        请求体字典。
    """
    return {
        "chat_session_id": session_id,
        "parent_message_id": None,
        "model_type": MODEL_TYPE_MAP.get(model, "default"),
        "prompt": prompt,
        "ref_file_ids": [],
        "thinking_enabled": False if model == MODEL_VISION else thinking,
        "search_enabled": search,
        "preempt": False,
        "client_stream_id": stream_id if stream_id is not None else make_stream_id(),
    }
