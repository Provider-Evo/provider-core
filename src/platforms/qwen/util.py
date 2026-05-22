"""Qwen 工具函数。"""

from __future__ import annotations
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)
QWEN_MODELS = ["qwen-turbo", "qwen-plus", "qwen-max", "qwen-max-longcontext", "qwen-vl-plus"]


def validate_model(model: str) -> bool:
    return model in QWEN_MODELS


def format_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    formatted = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role not in ("system", "user", "assistant", "tool"):
            role = "user"
        formatted.append({"role": role, "content": content})
    return formatted


def extract_content(response: Dict[str, Any]) -> str:
    try:
        choices = response.get("choices", [])
        if not choices:
            return ""
        return choices[0].get("message", {}).get("content", "")
    except (KeyError, IndexError):
        return ""
