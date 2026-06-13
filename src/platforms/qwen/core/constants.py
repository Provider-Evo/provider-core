from __future__ import annotations

"""Qwen 平台内部常量。

本模块承接所有平台级别的常量定义，包含：
- 端点根地址（BASE_URL）与浏览器标识（USER_AGENT）
- 支持的模型列表（MODELS）
- 平台能力字典（CAPS）
- 持久化路径（MODELS_PERSIST_PATH）
供 core/* 内部及 util.py 门面使用，禁止被 adapter.py 直接导入。
"""

from typing import Dict, Final, List

# ---------------------------------------------------------------------------
# 端点与浏览器标识
# ---------------------------------------------------------------------------

BASE_URL: Final[str] = "https://chat.qwen.ai"
"""Qwen 聊天服务根地址（无尾部斜杠）。"""

USER_AGENT: Final[str] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/148.0.0.0 Safari/537.36"
)
"""桌面浏览器 User-Agent。"""

# ---------------------------------------------------------------------------
# 支持的模型列表
# ---------------------------------------------------------------------------

MODELS: Final[List[str]] = [
    "qwen3.6-plus",
    "qwen3.5-plus",
    "qwen3.5-397b-a17b",
    "qwen3-max",
    "qwen3-max-2026-01-23",
    "qwen3-235b-a22b",
    "qwen3-30b-a3b",
    "qwen3-vl-30b-a3b",
    "qwen3-vl-32b",
    "qwen3-vl-plus",
    "qwen3-coder-plus",
    "qwen3-coder-30b-a3b-instruct",
    "qwen3-omni-flash",
    "qwen3-omni-flash-2025-12-01",
    "qwen2.5-72b-instruct",
    "qwen2.5-vl-32b-instruct",
    "qwen2.5-omni-7b",
    "qwen2.5-coder-32b-instruct",
    "qwen-max-latest",
    "qwen-plus-2025-07-28",
    "qwen-plus-2025-09-11",
    "qwen-plus-2025-01-25",
    "qwen-turbo-2025-02-11",
]
"""平台真实支持的模型 ID 列表，来源于 Qwen 官方 API 文档。"""

# ---------------------------------------------------------------------------
# 能力字典——仅声明平台真实支持的能力
# ---------------------------------------------------------------------------

CAPS: Final[Dict[str, bool]] = {
    "chat": True,
    "vision": True,
    "thinking": True,
    "search": True,
    "image_gen": True,
    "image_edit": True,
    "audio_gen": True,
    "video_gen": True,
    "continuation": True,
    "artifacts": True,
}
"""平台能力声明字典。

键对应 Candidate 字段，值均为 True（不支持的能力不写入）。
"""

# ---------------------------------------------------------------------------
# 持久化路径
# ---------------------------------------------------------------------------

MODELS_PERSIST_PATH: Final[str] = "persist/qwen/models.json"
"""模型列表持久化文件路径。"""
