
from __future__ import annotations

from typing import Awaitable, Callable

import aiohttp.web

from src.core.server.http.mw import _deny_unauthenticated, _is_auth_public
from src.foundation.config import get_config

__all__ = ["auth_middleware"]

_Handler = Callable[[aiohttp.web.Request], Awaitable[aiohttp.web.StreamResponse]]


@aiohttp.web.middleware
async def auth_middleware(
    request: aiohttp.web.Request,
    handler: _Handler,
) -> aiohttp.web.StreamResponse:
    """Reject unauthenticated requests to protected WebUI routes.

    Accept session cookie, API key, virtual key, or webui_token (Bearer / X-API-Key).
    Unauthenticated API clients receive HTTP 401 with an empty body.
    """
    path = request.path
    if request.method == "OPTIONS" or _is_auth_public(path):
        return await handler(request)

    cfg = get_config()
    from src.core.server.http.mw import _validate_credentials, _validate_webui_session

    if path.startswith("/v1/webui/"):
        if await _validate_webui_session(request, cfg):
            return await handler(request)
        return await _deny_unauthenticated(request, path)

    if await _validate_credentials(request, cfg):
        return await handler(request)

    return await _deny_unauthenticated(request, path)
