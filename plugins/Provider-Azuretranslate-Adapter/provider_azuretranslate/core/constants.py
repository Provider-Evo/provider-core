from __future__ import annotations

from typing import Dict, List

BASE_URL: str = "https://api.cognitive.microsofttranslator.com"
TRANSLATE_PATH: str = "/translate"
API_VERSION: str = "3.0"

# 默认语言
DEFAULT_TARGET_LANG: str = "en"
DEFAULT_SOURCE_LANG: str = ""  # 空 = 自动检测（不传 from 参数）

RATE_LIMIT_COOLDOWN: int = 60
RECOVERY_INTERVAL: int = 120

MODELS: List[str] = [
    "azuretranslate",
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
