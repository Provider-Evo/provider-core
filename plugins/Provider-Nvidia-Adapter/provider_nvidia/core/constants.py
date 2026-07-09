from __future__ import annotations

"""Nvidia 平台静态常量。"""

from typing import Dict, List

BASE_URL: str = "https://integrate.api.nvidia.com/v1"
CHAT_PATH: str = "/chat/completions"
MAX_TOKENS: int = 229376
RECOVERY_INTERVAL: int = 60

MODELS: List[str] = [
    "qwen/qwen3-coder-480b-a35b-instruct",
]

CAPS: Dict[str, bool] = {
    "chat": True,
    "tools": True,
}

FETCH_MODELS_ENABLED: bool = False
MODEL_FETCH_INTERVAL: int = 86400
