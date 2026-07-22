
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
    """Reject unauthenticated requests to protected WebUI routes.

Authentication is disabled when ``[auth] enabled = false`` in
``config.toml`` (the default). When enabled, accept session cookie,
API key, virtual key, or webui_token (Bearer / X-API-Key)."""
    cfg = get_config()
    if not cfg.auth.enabled:
        return await handler(request)

    path = request.path

    # Public paths bypass auth
    if _is_public(path):
        return await handler(request)

    from src.core.server.http.mw import _validate_credentials

    if await _validate_credentials(request, cfg):
        return await handler(request)

    # API routes return JSON 401; page routes redirect to /login
    if path.startswith("/v1/"):
        return aiohttp.web.json_response(
            {"error": {"message": "Unauthorized", "type": "auth_error"}},
            status=401,
        )
    raise aiohttp.web.HTTPFound("/login")
