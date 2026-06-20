from __future__ import annotations

from typing import Any

import aiohttp.web
from aiohttp.web_app import AppKey

from src.core.config import get_config
from src.core.errors import AuthError
from echotools.logger.manager import get_logger
from echotools.web.utils import (
    cors_middleware,
    error_middleware,
    json_response,
)

__all__ = ["create_app", "json_response", "REGISTRY_KEY", "SESSION_KEY"]
logger = get_logger(__name__)


# AppKey 类型定义，避免 NotAppKeyWarning
REGISTRY_KEY: AppKey[Any] = AppKey("registry")
SESSION_KEY: AppKey[Any] = AppKey("session")



_cors = cors_middleware(
    allow_headers="Content-Type, Authorization, X-API-Key, Anthropic-Version, x-api-key",
)


@aiohttp.web.middleware
async def _auth_middleware(
    request: aiohttp.web.Request,
    handler: Any,
) -> aiohttp.web.StreamResponse:
    # /login 必须无条件放行（登录入口）
    # /static/ 也必须放行（登录页与主页的 CSS/JS 依赖）
    # / 、/health 、/v1/models 均要求 pv2_session Cookie 或 Bearer/X-API-Key
    # 任一凭证有效才放行；浏览器无凭证 302 到 /login，API 客户端 JSON 401
    skip = {"/login"}
    if request.path in skip or request.method == "OPTIONS":
        return await handler(request)
    if request.path.startswith("/static/"):
        return await handler(request)

    cfg = get_config()
    if not cfg.auth.enabled:
        return await handler(request)

    group_id = request.headers.get("X-Group-Id", "")
    if group_id:
        group_id = group_id.strip()
        group_list = cfg.auth.group_list_set
        group_list_type = cfg.auth.group_list_type.lower().strip()

        if group_list_type == "blacklist" and group_id in group_list:
            return json_response(
                {
                    "error": {
                        "message": "Group is blocked",
                        "type": "authentication_error",
                        "code": "invalid_group",
                    }
                },
                status=401,
            )
        if group_list_type == "whitelist" and group_id not in group_list:
            return json_response(
                {
                    "error": {
                        "message": "Group is not allowed",
                        "type": "authentication_error",
                        "code": "invalid_group",
                    }
                },
                status=401,
            )

    if not cfg.auth.keys:
        return await handler(request)

    auth_header = request.headers.get("Authorization", "")
    api_key_header = request.headers.get("X-API-Key", "")

    token = ""
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif api_key_header:
        token = api_key_header.strip()
    else:
        # 浏览器访问：接受 pv2_session cookie 作为等价凭证
        cookie_token = request.cookies.get("pv2_session", "").strip()
        if cookie_token:
            token = cookie_token

    if token not in cfg.auth.keys:
        # 浏览器导航 -> 跳转登录页；API 客户端 -> 维持 JSON 401 协议
        accept = request.headers.get("Accept", "")
        if "text/html" in accept:
            raise aiohttp.web.HTTPFound("/login")
        return json_response(
            {
                "error": {
                    "message": "Invalid or missing API key",
                    "type": "authentication_error",
                    "code": "invalid_api_key",
                }
            },
            status=401,
        )
    return await handler(request)



_error = error_middleware(error_map={AuthError: (401, "authentication_error")})


async def create_app(registry: Any, session: Any) -> aiohttp.web.Application:
    """创建并配置 aiohttp Web 应用，挂载所有路由和中间件。

    Args:
        registry: 服务注册表实例，存入应用上下文。
        session: 会话管理实例，存入应用上下文。

    Returns:
        aiohttp.web.Application: 配置完成的 Web 应用。
    """
    from src.routes.anthropic import setup_routes as setup_anth
    from src.routes.openai import setup_routes as setup_oai
    from src.routes.static import setup_routes as setup_static
    from src.webui.routes import setup_routes as setup_webui
    from src.webui.middleware.static_nocache import static_nocache_middleware
    from src.webui.middleware.stats import stats_middleware

    app = aiohttp.web.Application(
        middlewares=[_cors, _auth_middleware, stats_middleware, static_nocache_middleware, _error],
        client_max_size=100 * 1024 * 1024,  # 100MB
    )

    app[REGISTRY_KEY] = registry
    app[SESSION_KEY] = session

    setup_static(app)
    setup_oai(app)
    setup_anth(app)
    setup_webui(app)

    async def _on_startup(application: aiohttp.web.Application) -> None:
        logger.debug("aiohttp.web 应用已启动")
        # Start stats persistence (load from disk + periodic save)
        try:
            from src.webui.services.stats import start_persist
            start_persist()
        except Exception:
            pass
        # Start request log persistence (load from disk + periodic save)
        try:
            from src.webui.services.request_log import start_request_persist
            start_request_persist()
        except Exception:
            pass
        # 将 loguru 日志连接到 WebUI WebSocket（在事件循环启动后）
        try:
            from src.webui.logs_ws import log_broker, setup_loguru_sink
            import asyncio
            loop = asyncio.get_running_loop()
            log_broker.set_loop(loop)
            setup_loguru_sink()
        except Exception:
            pass
        # Recover terminal sessions from persist store
        try:
            from src.core.terminal_sessions import get_terminal_store
            from src.webui.routers.terminal import recover_sessions
            store = get_terminal_store()
            await recover_sessions(store)
        except Exception:
            pass

    async def _on_cleanup(application: aiohttp.web.Application) -> None:
        logger.info("aiohttp.web 应用正在清理")
        # Final stats save on shutdown
        try:
            from src.webui.services.stats import save_stats
            save_stats()
        except Exception:
            pass
        # Save all terminal session states for crash recovery
        try:
            from src.core.terminal_sessions import get_terminal_store
            from src.webui.routers.terminal import list_sessions
            store = get_terminal_store()
            for session in list_sessions():
                if session._terminal and session.alive:
                    session._terminal.save_state(store.persist_dir)
        except Exception:
            pass

    app.on_startup.append(_on_startup)
    app.on_cleanup.append(_on_cleanup)

    return app
