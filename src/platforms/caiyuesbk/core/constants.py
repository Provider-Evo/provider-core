"""caiyuesbk 平台常量定义。

BASE_URL / 模型 / 能力等平台级常量统一在此维护。
"""

from __future__ import annotations

BASE_URL = "https://caiyuesbk.top:16188"
CHAT_PATH = "/v1/chat/completions"

# 硬编码兜底模型列表
MODELS: list[str] = [
    "Qwen3-32B-siliconflow",
    "glm-4.6-siliconflow",
    "qwen3-80b",
    "kimi-k2",
    "kimi-k2-thinking",
    "deepseek-v3.1-terminus",
    "deepseek-v3.1",
    "deepseek-v3.2-siliconflow",
    "glm4.7",
    "kimi-k2-instruct-0905",
    "qwen3.5-122b",
    "gpt-oss-120b",
    "glm-4.6V-siliconflow",
    "kimi-k2-siliconflow",
]

# 能力配置
CAPS: dict[str, bool] = {
    "chat": True,
    "tools": True,
    "thinking": True,
    "vision": True,
}

# 是否允许远程模型列表覆盖本地（True=覆盖，False=只增不减）
FETCH_MODELS_ENABLED: bool = True

# 远程模型刷新间隔（秒），默认 24 小时
MODEL_FETCH_INTERVAL: int = 86400
