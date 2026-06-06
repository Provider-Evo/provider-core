"""Chutes 平台常量定义。

所有字段（BASE_URL / 模型 / 能力）均为静态常量。
BASE_URL 等部署端点只在平台代码内维护，不进 ``config.toml``。
"""

from __future__ import annotations

BASE_URL = "https://llm.chutes.ai"
CHAT_PATH = "/v1/chat/completions"

# 硬编码模型列表——兜底，始终存在
MODELS: list[str] = [
    "Alibaba-NLP/Tongyi-DeepResearch-30B-A3B",
]

# 能力字典
CAPS: dict[str, bool] = {
    "chat": True,
}

# 是否允许用远程模型列表覆盖本地（True=覆盖，False=只增不减）
FETCH_MODELS_ENABLED: bool = False

# 远程模型刷新间隔（秒），默认24小时
MODEL_FETCH_INTERVAL: int = 86400
