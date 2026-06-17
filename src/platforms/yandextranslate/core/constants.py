from __future__ import annotations

from typing import Dict, List

BASE_URL: str = "https://translate.api.cloud.yandex.net"
TRANSLATE_PATH: str = "/translate/v2/translate"

# 默认语言
DEFAULT_TARGET_LANG: str = "en"
DEFAULT_SOURCE_LANG: str = ""  # 空 = 自动检测

RATE_LIMIT_COOLDOWN: int = 60
RECOVERY_INTERVAL: int = 120

MODELS: List[str] = [
    "yandextranslate",
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
