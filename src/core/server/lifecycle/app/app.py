"""app 模块 — 项目标准模块。

职责：
    作为 Provider-Evo 项目标准模块，提供 app 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""



from typing import Any

import aiohttp.web

from src.core.server.lifecycle.net.keys import REGISTRY_KEY, SESSION_KEY

__all__ = ["create_app", "REGISTRY_KEY", "SESSION_KEY"]


async def create_app(registry: Any, session: Any) -> aiohttp.web.Application:
    """创建并配置 aiohttp 应用（委托 bootstrap 组合根）。"""
    from src.bootstrap.app_factory import create_application

    return await create_application(registry, session)
