from __future__ import annotations

"""Ollama 平台核心常量。

包含 URL、发现配置等编译时常量。
持久化路径（SRV_FILE / REG_FILE）保留在 util 层管理，因为它们属于运行时配置。
"""

from typing import Dict, List

# ── URL常量 ──────────────────────────────────────────────
BASE_URL: str = "https://freeollama.oneplus1.top"
CHAT_PATH: str = "/api/chat"
EMBED_PATH: str = "/api/embed"

# ── 发现配置 ──────────────────────────────────────────────
PAGE_SIZE: int = 100
TIMEOUT: int = 10
MAX_WORKERS: int = 512
REFRESH_INTERVAL: int = 86400

# ── 能力声明 ──────────────────────────────────────────────
CAPS: Dict[str, bool] = {
    "chat": True,
    "embedding": True,
}

# ── 模型列表 ──────────────────────────────────────────────
# Ollama 使用动态发现，初始为空列表
MODELS: List[str] = []

# ── 模型缓存配置 ──────────────────────────────────────────
FETCH_MODELS_ENABLED: bool = False
MODEL_FETCH_INTERVAL: int = 86400

# ── 动态发现开关 ──────────────────────────────────────────
DYNAMIC_DISCOVERY: bool = True  # 是否动态从网络获取服务器列表；False 时仅使用持久化缓存

# ── 模型过滤 ──────────────────────────────────────────────
FILTER_CLOUD_MODELS: bool = True  # 过滤 :cloud 后缀的模型（需付费的云端模型）
