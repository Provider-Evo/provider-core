from __future__ import annotations

from typing import Dict, List

# DeepL 端点（按 Key 类型自动选择）
FREE_BASE_URL: str = "https://api-free.deepl.com"
PAID_BASE_URL: str = "https://api.deepl.com"
TRANSLATE_PATH: str = "/v2/translate"

# 默认目标语言
DEFAULT_TARGET_LANG: str = "EN"
DEFAULT_SOURCE_LANG: str = ""  # 空 = 自动检测

RATE_LIMIT_COOLDOWN: int = 60
RECOVERY_INTERVAL: int = 120

# 模型名称（翻译平台用统一模型名）
MODELS: List[str] = [
    "deepl-translate",
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
