from __future__ import annotations

"""单一组合根 — 组装 aiohttp 应用、中间件与路由。"""

from typing import Any

import aiohttp.web

from src.bootstrap.lifecycle import on_cleanup, on_startup
from src.bootstrap.webui_bindings import log_webui_token_if_enabled, register_webui_bindings
from src.core.utils.observability import OBSERVABILITY_KEY, ObservabilityServices
from src.core.server.net.keys import REGISTRY_KEY, SESSION_KEY
from src.core.server.http.middleware import _auth_middleware, _cors, _error

__all__ = ["create_application"]


async def create_application(
    registry: Any,
    session: Any,
    *,
    observability: ObservabilityServices | None = None,
) -> aiohttp.web.Application:
    """创建并配置完整 Provider 应用（API + WebUI）。"""
    from src.routes.anthropic import setup_routes as setup_anth
    from src.routes.main import setup_routes as setup_main
    from src.routes.openai import setup_routes as setup_oai
    from src.webui.bootstrap.routes import setup_routes as setup_webui
    from src.webui.internal.middleware.static_nocache import static_nocache_middleware
    from src.webui.internal.middleware.stats import stats_middleware

    obs = observability or register_webui_bindings()
    log_webui_token_if_enabled()

    app = aiohttp.web.Application(
        middlewares=[_cors, _auth_middleware, stats_middleware, static_nocache_middleware, _error],
        client_max_size=100 * 1024 * 1024,
    )
    app[REGISTRY_KEY] = registry
    app[SESSION_KEY] = session
    app[OBSERVABILITY_KEY] = obs

    setup_main(app)
    setup_oai(app)
    setup_anth(app)
    setup_webui(app)
    from src.bootstrap.plugin_routes import register_plugin_routes

    register_plugin_routes(app)

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app
