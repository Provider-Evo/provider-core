from __future__ import annotations

"""CodeBuddy 平台常量定义。"""

from typing import Dict, List

# ── 服务端点 ────────────────────────────────────────────────────────────────────
BASE_URL: str = "https://www.codebuddy.ai"
CHAT_PATH: str = "/v2/chat/completions"
IDE_VERSION: str = "1.0.7"

# ── 模型列表 ────────────────────────────────────────────────────────────────────
MODELS: List[str] = [
    "auto-chat",
]

# ── 能力字典 ────────────────────────────────────────────────────────────────────
CAPS: Dict[str, bool] = {
    "chat": True,
}

# ── 模型获取 ────────────────────────────────────────────────────────────────────
FETCH_MODELS_ENABLED: bool = False
MODEL_FETCH_INTERVAL: int = 86400
