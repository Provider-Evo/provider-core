"""auth 模块 — WebUI 层。

职责：
    作为 Provider-Evo 项目标准模块，提供 auth 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""

from __future__ import annotations

from typing import Awaitable, Callable

import aiohttp.web

from src.foundation.config import get_config
from src.webui.internal.core.auth import COOKIE_NAME

__all__ = ["auth_middleware"]

_Handler = Callable[[aiohttp.web.Request], Awaitable[aiohttp.web.StreamResponse]]

# Paths that do NOT require authentication
_PUBLIC_PATHS: frozenset[str] = frozenset(
    {
        "/login",
        "/logout",
        "/v1/health",
        "/v1/webui/auth/verify",
    }
)

# Path prefixes that do NOT require authentication
_PUBLIC_PREFIXES: tuple[str, ...] = (
    "/static/",
    "/favicon",
)


def _is_public(path: str) -> bool:
    """Return True if *path* is exempt from auth checks."""
    if path in _PUBLIC_PATHS:
        return True
    for prefix in _PUBLIC_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


@aiohttp.web.middleware
async def auth_middleware(
    request: aiohttp.web.Request,
    handler: _Handler,
) -> aiohttp.web.StreamResponse:
    """中文说明：auth_middleware。

    Reject unauthenticated requests to protected WebUI routes.

    Authentication is disabled when ``[auth] enabled = false`` in
    ``config.toml`` (the default)."""
    cfg = get_config()
    if not cfg.auth.enabled:
        return await handler(request)

    path = request.path

    # Public paths bypass auth
    if _is_public(path):
        return await handler(request)

    # Check cookie
    cookie_val = request.cookies.get(COOKIE_NAME, "")
    if cookie_val:
        from src.webui.internal.core.secure import token_manager

        if token_manager.verify(cookie_val):
            return await handler(request)

    # API routes return JSON 401; page routes redirect to /login
    if path.startswith("/v1/"):
        return aiohttp.web.json_response(
            {"error": {"message": "Unauthorized", "type": "auth_error"}},
            status=401,
        )
    raise aiohttp.web.HTTPFound("/login")
