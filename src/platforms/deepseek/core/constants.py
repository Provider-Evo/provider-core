from __future__ import annotations

# src/platforms/deepseek/core/constants.py
"""DeepSeek 平台常量定义"""

from typing import Dict, List

# ── 模型 ────────────────────────────────────────────────────────────────────
MODEL_PRO: str = "deepseek-v4-pro"
MODEL_FLASH: str = "deepseek-v4-flash"
MODEL_VISION: str = "deepseek-v4-vision"
MODELS: List[str] = [MODEL_PRO, MODEL_FLASH, MODEL_VISION]

# ── 模型映射到 DeepSeek 内部模型类型 ────────────────────────────────────────
# deepseek-v4-pro    → default
# deepseek-v4-flash  → flash
# deepseek-v4-vision → vision
MODEL_TYPE_MAP: Dict[str, str] = {
    MODEL_PRO: "default",
    MODEL_FLASH: "flash",
    MODEL_VISION: "vision",
}

# ── 能力字典 ─────────────────────────────────────────────────────────────────
# pro 和 flash 均支持联网搜索与思考（由请求参数控制）
_BASE_CAPS: Dict[str, bool] = {
    "chat": True,
    "thinking": True,
    "search": True,
    "tools": True,
    "continuation": True,
}

CAPS_PRO: Dict[str, bool] = dict(_BASE_CAPS)
CAPS_FLASH: Dict[str, bool] = dict(_BASE_CAPS)

# vision 模型：仅保留支持能力
CAPS_VISION: Dict[str, bool] = {
    "chat": True,
    "vision": True,
}

# 三模型能力并集（用于 /v1/models 输出）
CAPS: Dict[str, bool] = dict(_BASE_CAPS)
CAPS["vision"] = CAPS_VISION["vision"]

# ── 服务端点 ──────────────────────────────────────────────────────────────────
DEFAULT_HOST: str = "chat.deepseek.com"
HIF_LEIM_URL: str = "https://hif-leim.deepseek.com/query"
HIF_DLIQ_URL: str = "https://hif-dliq.deepseek.com/query"

# ── WASM PoW ──────────────────────────────────────────────────────────────────
WASM_PATH: str = "persist/deepseek/sha3_wasm_bg.7b9ca65ddd.wasm"
WASM_URL: str = (
    "https://fe-static.deepseek.com/chat/static/sha3_wasm_bg.7b9ca65ddd.wasm"
)
WASM_META: str = "persist/deepseek/wasm_meta.json"

# ── 其他 ──────────────────────────────────────────────────────────────────────
MAX_CONTINUE: int = 10
MAX_RETRIES: int = 3
FETCH_MODELS_ENABLED: bool = False
MODEL_FETCH_INTERVAL: int = 86400
HIF_REFRESH_INTERVAL: float = 2700.0  # 秒，45 分钟

# ── 公共请求头 ────────────────────────────────────────────────────────────────
COMMON_HEADERS: Dict[str, str] = {
    "accept": "*/*",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
    "content-type": "application/json",
    "sec-ch-ua": (
        '"Chromium";v="146","Not-A.Brand";v="24","Google Chrome";v="146"'
    ),
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/146.0.0.0 Safari/537.36"
    ),
    "x-app-version": "20241129.1",
    "x-client-locale": "zh_CN",
    "x-client-platform": "web",
    "x-client-timezone-offset": "28800",
    "x-client-version": "2.0.0",
}
