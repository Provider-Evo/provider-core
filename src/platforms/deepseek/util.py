"""DeepSeek 工具函数。"""

from __future__ import annotations
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)
DEEPSEEK_MODELS = ["deepseek-chat", "deepseek-coder", "deepseek-coder-instruct"]


def validate_model(model: str) -> bool:
    return model in DEEPSEEK_MODELS


def format_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    formatted = []
    for msg in messages:
        role = msg.get("role", "user")
        if role not in ("system", "user", "assistant", "tool"):
            role = "user"
        formatted.append({"role": role, "content": msg.get("content", "")})
    return formatted
