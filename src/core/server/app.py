from __future__ import annotations

"""aiohttp application creation and lifecycle hooks."""

import asyncio
from typing import Any

import aiohttp.web
from aiohttp.web_app import AppKey

from echotools.logger.manager import get_logger

from src.core.server.middleware import _auth_middleware, _cors, _error

__all__ = ["create_app", "REGISTRY_KEY", "SESSION_KEY"]

logger = get_logger(__name__)

# AppKey type definitions to avoid NotAppKeyWarning
REGISTRY_KEY: AppKey[Any] = AppKey("registry")
SESSION_KEY: AppKey[Any] = AppKey("session")


async def create_app(registry: Any, session: Any) -> aiohttp.web.Application:
    """Create and configure aiohttp web application with all routes and middleware.

    Args:
        registry: Service registry instance, stored in ``app[REGISTRY_KEY]``.
        session: HTTP session instance, stored in ``app[SESSION_KEY]``.

    Returns:
        Configured aiohttp.web.Application instance.

    Middleware order (outer to inner):
        CORS -> Auth -> Stats -> StaticNoCache -> Error
    """
    from src.routes.anthropic import setup_routes as setup_anth
    from src.routes.openai import setup_routes as setup_oai
    from src.routes.main import setup_routes as setup_main
    from src.webui.middleware.static_nocache import static_nocache_middleware
    from src.webui.middleware.stats import stats_middleware
    from src.webui.routes import setup_routes as setup_webui

    app = aiohttp.web.Application(
        middlewares=[
            _cors,
            _auth_middleware,
            stats_middleware,
            static_nocache_middleware,
            _error,
        ],
        client_max_size=100 * 1024 * 1024,  # 100MB
    )

    app[REGISTRY_KEY] = registry
    app[SESSION_KEY] = session

    setup_main(app)
    setup_oai(app)
    setup_anth(app)
    setup_webui(app)

    async def _on_startup(application: aiohttp.web.Application) -> None:
        """Startup hook — load persisted data, start background tasks."""
        logger.debug("aiohttp.web application started")

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
            from src.webui.logs_ws import log_broker, setup_loguru_sink
            loop = asyncio.get_running_loop()
            log_broker.set_loop(loop)
            setup_loguru_sink()
        except Exception:
            pass

        try:
            from src.core.terminal_sessions import get_terminal_store
            from src.webui.routers.terminal import recover_sessions
            store = get_terminal_store()
            await recover_sessions(store)
        except Exception:
            pass

    async def _on_cleanup(application: aiohttp.web.Application) -> None:
        """Cleanup hook — save persisted data, graceful shutdown."""
        logger.info("aiohttp.web application cleaning up")

        try:
            from src.webui.services.stats import save_stats
            save_stats()
        except Exception:
            pass

        try:
            from src.core.terminal_sessions import get_terminal_store
            from src.webui.routers.terminal import list_sessions
            store = get_terminal_store()
            for session_obj in list_sessions():
                if session_obj._terminal and session_obj.alive:
                    session_obj._terminal.save_state(store.persist_dir)
        except Exception:
            pass

    app.on_startup.append(_on_startup)
    app.on_cleanup.append(_on_cleanup)

    return app
