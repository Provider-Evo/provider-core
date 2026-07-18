"""constants 模块 — Provider 适配器层。

职责：
    集中放置 provider 常量定义（模型名、URL 模板、错误码等）。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""



from __future__ import annotations

BASE_URL = "https://api.airforce"
CHAT_PATH = "/v1/chat/completions"
MODELS_PATH = "/v1/models"

MODELS: list[str] = ["roleplay:free"]
CAPS: dict[str, bool] = {
    "chat": True,
    "completions": True,
    "responses": True,
    "tools": True,
    "native_tools": True,
}
