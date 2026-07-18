"""keys 模块 — 项目标准模块。

职责：
    作为 Provider-Evo 项目标准模块，提供 keys 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""


from typing import Any

from aiohttp.web_app import AppKey

REGISTRY_KEY: AppKey[Any] = AppKey("registry")
SESSION_KEY: AppKey[Any] = AppKey("session")

__all__ = ["REGISTRY_KEY", "SESSION_KEY"]
