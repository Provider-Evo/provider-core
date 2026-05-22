from __future__ import annotations

import json
import time
from typing import Any, Awaitable, Callable, Optional

import aiohttp.web

from src.core.config import get_config
from src.core.http import json_response
from src.logger import get_logger

__all__ = ["create_app"]
logger = get_logger(__name__)

_Handler = Callable[[aiohttp.web.Request], Awaitable[aiohttp.web.StreamResponse]]


def _json_response(data: Any, status: int = 200, headers: Optional[dict] = None) -> aiohttp.web.Response:
    body = json.dumps(data, ensure_ascii=False)
    resp_headers = {"Content-Type": "application/json"}
    if headers:
        resp_headers.update(headers)
    return aiohttp.web.Response(body=body.encode("utf-8"), status=status, headers=resp_headers)


def _check_group_auth(cfg: Any, token: str) -> bool:
    """检查组级别认证。"""
    if cfg.auth.group_list_type == "blacklist":
        return token not in cfg.auth.group_list
    elif cfg.auth.group_list_type == "whitelist":
        return token in cfg.auth.group_list
    return True


@aiohttp.web.middleware
async def _cors_middleware(request: aiohttp.web.Request, handler: _Handler) -> aiohttp.web.StreamResponse:
    if request.method == "OPTIONS":
        return aiohttp.web.Response(status=204, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-API-Key, Anthropic-Version, x-api-key",
            "Access-Control-Max-Age": "86400",
        })
    resp = await handler(request)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


@aiohttp.web.middleware
async def _auth_middleware(request: aiohttp.web.Request, handler: _Handler) -> aiohttp.web.StreamResponse:
    cfg = get_config()
    if not cfg.auth.enabled or not cfg.auth.keys:
        return await handler(request)
    skip = {"/", "/health", "/docs", "/v1/models"}
    if request.path in skip or request.method == "OPTIONS":
        return await handler(request)
    auth_header = request.headers.get("Authorization", "")
    api_key_header = request.headers.get("X-API-Key", "") or request.headers.get("x-api-key", "")
    token = ""
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif api_key_header:
        token = api_key_header.strip()
    if token not in cfg.auth.keys:
        return json_response({"error": {"message": "Invalid or missing API key", "type": "authentication_error"}}, status=401)
    if not _check_group_auth(cfg, token):
        return json_response({"error": {"message": "Access denied by group policy", "type": "authorization_error"}}, status=403)
    return await handler(request)


@aiohttp.web.middleware
async def _error_middleware(request: aiohttp.web.Request, handler: _Handler) -> aiohttp.web.StreamResponse:
    try:
        return await handler(request)
    except aiohttp.web.HTTPException:
        raise
    except Exception as e:
        logger.error("未捕获异常: %s %s -> %s", request.method, request.path, e)
        return json_response({"error": {"message": str(e), "type": "server_error"}}, status=500)


async def create_app(session: Any) -> aiohttp.web.Application:
    from src.routes.chat import setup_routes as setup_chat
    from src.routes.models import setup_routes as setup_models
    from src.routes.function_call import setup_routes as setup_fncall
    from src.routes.health import setup_routes as setup_health

    app = aiohttp.web.Application(
        middlewares=[_cors_middleware, _auth_middleware, _error_middleware],
        client_max_size=100 * 1024 * 1024,
    )
    app["session"] = session
    setup_chat(app)
    setup_models(app)
    setup_fncall(app)
    setup_health(app)

    async def _on_startup(application: aiohttp.web.Application) -> None:
        logger.info("aiohttp.web 应用已启动")

    async def _on_cleanup(application: aiohttp.web.Application) -> None:
        logger.info("aiohttp.web 应用正在清理")

    app.on_startup.append(_on_startup)
    app.on_cleanup.append(_on_cleanup)
    return app
