"""WebUI 应用工厂。"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Optional

import aiohttp.web
from aiohttp.web_app import AppKey

from src.logger import get_logger
from src.webui.bootstrap.dependencies import get_server_config
from src.webui.middleware import auth_middleware, error_middleware, static_nocache_middleware
from src.webui.bootstrap.routes import setup_routes

__all__ = ["WEBUI_CONFIG_KEY", "create_app"]

WEBUI_CONFIG_KEY: AppKey[Any] = AppKey("webui_config")

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
logger = get_logger(__name__)


def create_app(registry: Optional[Any] = None, server: Optional[Any] = None) -> aiohttp.web.Application:
    """创建独立 WebUI 应用。"""
    app = aiohttp.web.Application(middlewares=[auth_middleware, static_nocache_middleware, error_middleware])
    if registry is not None:
        app["registry"] = registry
    if server is not None:
        app["webui_server"] = server
    config = get_server_config()
    app[WEBUI_CONFIG_KEY] = config.to_dict()
    setup_routes(app)

    async def _on_startup(application: aiohttp.web.Application) -> None:
        """启动钩子 — 加载持久化数据。"""
        # Show webui_token in log for first-time setup
        from src.core.config import get_config
        from src.webui.core.security import token_manager
        cfg = get_config()
        if cfg.auth.enabled:
            logger.info("WebUI Token: %s", token_manager.token)

        try:
            from src.webui.services.stats import start_persist
            start_persist()
        except Exception:
            pass

        try:
            from src.webui.services.request_log import start_request_persist
            start_request_persist()
        except Exception:
            pass

        try:
            from src.webui.core.logs_ws import log_broker, setup_loguru_sink
            loop = asyncio.get_running_loop()
            log_broker.set_loop(loop)
            setup_loguru_sink()
        except Exception:
            pass

    app.on_startup.append(_on_startup)
    return app
