"""constants 模块 — Provider 适配器层。

职责：
    集中放置 provider 常量定义（模型名、URL 模板、错误码等）。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
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
    "completions": True,
    "responses": True,
    "tools": True,
    "native_tools": True,
    "thinking": True,
    "vision": True,
}

# 是否允许远程模型列表覆盖本地（True=覆盖，False=只增不减）
FETCH_MODELS_ENABLED: bool = True

# 远程模型刷新间隔（秒），默认 24 小时
MODEL_FETCH_INTERVAL: int = 86400
