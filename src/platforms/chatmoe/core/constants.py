"""ChatMoe 平台常量定义。

BASE_URL / 模型 / 能力等平台级常量统一在此维护。
"""

from __future__ import annotations

BASE_URL = "https://chatmoe.cn"
CHAT_PATH = "/api/chat"

# 硬编码模型列表——兜底，始终存在
MODELS: list[str] = [
    "glm-4.5-flash",
]

# 能力字典——ChatMoe 支持聊天、深度思考、联网搜索
CAPS: dict[str, bool] = {
    "chat": True,
    "thinking": True,
    "search": True,
}

# 是否允许用远程模型列表覆盖本地（ChatMoe 无公开模型接口，保持本地列表）
FETCH_MODELS_ENABLED: bool = False

# 远程模型刷新间隔（秒），默认 24 小时
MODEL_FETCH_INTERVAL: int = 86400
