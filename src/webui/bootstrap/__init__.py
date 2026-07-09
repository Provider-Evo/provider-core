from __future__ import annotations

"""WebUI 启动与路由装配包。"""

from .app import WEBUI_CONFIG_KEY, create_app
from .routes import setup_routes
from .server import ThreadedWebUIServer, WebUIServer

__all__ = [
    "WEBUI_CONFIG_KEY",
    "ThreadedWebUIServer",
    "WebUIServer",
    "create_app",
    "setup_routes",
]
