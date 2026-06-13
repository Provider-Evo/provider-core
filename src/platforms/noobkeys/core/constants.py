from __future__ import annotations

from typing import Dict, List

BASE_URL: str = "https://noobkeys.onrender.com/v1"
CHAT_PATH: str = "/chat/completions"
MODELS_PATH: str = "/models"

RATE_LIMIT_COOLDOWN: int = 60
RECOVERY_INTERVAL: int = 120

MODELS: List[str] = [
    "claude-opus-4-5-20251101",
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-5-20250929",
    "claude-sonnet-4-20250514",
    "claude-3-7-sonnet-20250219",
    "claude-3-5-haiku-latest",
    "moonshotai/kimi-k2-instruct-0905",
    "openai/gpt-oss-120b",
    "qwen/qwen3-32b",
]

CAPS: Dict[str, bool] = {
    "chat": True,
    "vision": False,
    "tools": False,
    "thinking": False,
    "search": False,
    "embedding": False,
}

FETCH_MODELS_ENABLED: bool = False
MODEL_FETCH_INTERVAL: int = 86400
