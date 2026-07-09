from __future__ import annotations

"""aiohttp application keys and thin factory wrapper."""

from typing import Any

import aiohttp.web

from src.bootstrap.app_factory import create_application
from src.core.server.net.keys import REGISTRY_KEY, SESSION_KEY

__all__ = ["create_app", "REGISTRY_KEY", "SESSION_KEY"]


async def create_app(registry: Any, session: Any) -> aiohttp.web.Application:
    """创建并配置 aiohttp 应用（委托 bootstrap 组合根）。"""
    return await create_application(registry, session)
