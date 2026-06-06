"""Cerebras 平台常量定义。

模型 / 能力等平台级常量统一在此维护。
Cerebras 使用官方 SDK，无需 BASE_URL。
"""

from __future__ import annotations

# 硬编码模型列表——兜底，始终存在
MODELS: list[str] = [
    "gpt-oss-120b",
    "llama-3.3-70b",
    "llama-4-maverick-17b-128e-instruct",
    "llama-4-scout-17b-16e-instruct",
    "llama3.1-8b",
    "qwen-3-235b-a22b-instruct-2507",
    "qwen-3-235b-a22b-thinking-2507",
    "qwen-3-32b",
    "qwen-3-coder-480b",
]

# 能力字典——Cerebras 支持 chat 和 tools
CAPS: dict[str, bool] = {
    "chat": True,
    "tools": True,
}

# 是否允许用远程模型列表覆盖本地（Cerebras SDK 可查询模型列表）
FETCH_MODELS_ENABLED: bool = False

# 远程模型刷新间隔（秒），默认 24 小时
MODEL_FETCH_INTERVAL: int = 86400
