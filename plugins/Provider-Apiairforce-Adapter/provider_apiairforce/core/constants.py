"""apiairforce 平台常量定义。

BASE_URL / 模型 / 能力等平台级常量统一在此维护。
"""

from __future__ import annotations

BASE_URL = "https://api.airforce"
CHAT_PATH = "/v1/chat/completions"
MODELS_PATH = "/v1/models"

MODELS: list[str] = ["roleplay:free"]
CAPS: dict[str, bool] = {"chat": True}
