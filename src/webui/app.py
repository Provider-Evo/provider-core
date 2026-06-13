from __future__ import annotations

"""WebUI 应用工厂。"""

from pathlib import Path
from typing import Any, Optional

import aiohttp.web
from aiohttp.web_app import AppKey

from src.webui.dependencies import get_server_config
from src.webui.middleware import error_middleware, static_nocache_middleware
from src.webui.routes import setup_routes

__all__ = ["WEBUI_CONFIG_KEY", "create_app"]

WEBUI_CONFIG_KEY: AppKey[Any] = AppKey("webui_config")

_STATIC_DIR = Path(__file__).parent / "static"


def create_app(registry: Optional[Any] = None, server: Optional[Any] = None) -> aiohttp.web.Application:
    """创建独立 WebUI 应用。"""
    app = aiohttp.web.Application(middlewares=[static_nocache_middleware, error_middleware])
    if registry is not None:
        app["registry"] = registry
    if server is not None:
        app["webui_server"] = server
    config = get_server_config()
    app[WEBUI_CONFIG_KEY] = config.to_dict()
    setup_routes(app)
    return app
