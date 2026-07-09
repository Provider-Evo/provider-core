from __future__ import annotations

"""N1N 平台常量定义。"""

from typing import Dict, List

from .models import MODELS

# ── 服务端点 ────────────────────────────────────────────────────────────────────
BASE_URL: str = "https://api.n1n.ai"
CHAT_PATH: str = "/pg/chat/completions"
MODELS_PATH: str = "/api/user/models?group=default"

# ── 能力字典 ────────────────────────────────────────────────────────────────────
CAPS: Dict[str, bool] = {
    "chat": True,
}

# ── 模型获取 ────────────────────────────────────────────────────────────────────
FETCH_MODELS_ENABLED: bool = False
MODEL_FETCH_INTERVAL: int = 86400
