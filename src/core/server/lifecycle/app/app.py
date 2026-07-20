
from typing import Any

import aiohttp.web

from src.core.server.lifecycle.net.keys import REGISTRY_KEY, SESSION_KEY

__all__ = ["create_app", "REGISTRY_KEY", "SESSION_KEY"]


async def create_app(registry: Any, session: Any) -> aiohttp.web.Application:
    """创建并配置 aiohttp 应用（委托 bootstrap 组合根）。"""
    from src.bootstrap.app_factory import create_application

    return await create_application(registry, session)
