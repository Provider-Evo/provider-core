from __future__ import annotations

from typing import Dict, List

BASE_URL: str = "https://translate-pa.googleapis.com"
TRANSLATE_PATH: str = "/v1/translateHtml"

# 硬编码公共 API Key
API_KEY: str = "AIzaSyA6EEtrRfV7-fBU2dJ5V4v0VjK0V4v0V4"

# 默认语言
DEFAULT_TARGET_LANG: str = "en"
DEFAULT_SOURCE_LANG: str = "auto"

RATE_LIMIT_COOLDOWN: int = 30
RECOVERY_INTERVAL: int = 60

MODELS: List[str] = [
    "googletranslate",
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
