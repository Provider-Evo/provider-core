from __future__ import annotations

"""WebUI 应用工厂。"""

from pathlib import Path
from typing import Any, Optional

import aiohttp.web
from aiohttp.web_app import AppKey

from src.webui.dependencies import get_server_config
from src.webui.middleware import error_middleware
from src.webui.routes import setup_routes

__all__ = ["WEBUI_CONFIG_KEY", "create_app", "render_page"]

WEBUI_CONFIG_KEY: AppKey[Any] = AppKey("webui_config")

_STATIC_DIR = Path(__file__).parent / "static"


def render_page(page: str = "webui") -> str:
    """渲染页面（向后兼容，返回静态 HTML）。"""
    html_file = _STATIC_DIR / ("docs.html" if page == "docs" else "index.html")
    if html_file.exists():
        return html_file.read_text(encoding="utf-8")
    return "<!doctype html><html><head><title>Not Found</title></head><body>Static files not found</body></html>"


def create_app(registry: Optional[Any] = None, server: Optional[Any] = None) -> aiohttp.web.Application:
    """创建独立 WebUI 应用。"""
    app = aiohttp.web.Application(middlewares=[error_middleware])
    if registry is not None:
        app["registry"] = registry
    if server is not None:
        app["webui_server"] = server
    config = get_server_config()
    app[WEBUI_CONFIG_KEY] = config.to_dict()
    setup_routes(app)
    return app
