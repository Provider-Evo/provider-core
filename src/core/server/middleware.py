from __future__ import annotations

"""aiohttp middleware: CORS, authentication, error handling."""

from typing import Any

import aiohttp.web

from echotools.web.utils import cors_middleware, error_middleware, json_response

from src.core.config import get_config
from src.core.errors import AuthError

__all__ = ["_cors", "_auth_middleware", "_error"]

_cors = cors_middleware(
    allow_headers=(
        "Content-Type, Authorization, X-API-Key, "
        "Anthropic-Version, x-api-key"
    ),
)


@aiohttp.web.middleware
async def _auth_middleware(
    request: aiohttp.web.Request,
    handler: Any,
) -> aiohttp.web.StreamResponse:
    """Authentication middleware — checks API Key / Session Cookie / Group whitelist/blacklist.

    Pass-through rules:
    - ``/login`` and ``/static/`` pass unconditionally
    - OPTIONS requests pass unconditionally (CORS preflight)
    - All requests pass when auth is not enabled

    Auth flow (when auth.enabled=true):
    1. Check Group whitelist/blacklist (``X-Group-Id`` header)
    2. Check API Key (``Authorization: Bearer xxx`` or ``X-API-Key``)
       or Session Cookie (``pv2_session``)
    3. Invalid credentials:
       - Browser (``Accept: text/html``): 302 redirect to ``/login``
       - API client: JSON 401
    """
    skip = {"/login", "/health"}
    if request.path in skip or request.method == "OPTIONS":
        return await handler(request)
    if request.path.startswith("/static/"):
        return await handler(request)

    cfg = get_config()
    if not cfg.auth.enabled:
        return await handler(request)

    # --- Group whitelist/blacklist check ---
    group_id = request.headers.get("X-Group-Id", "").strip()
    if group_id:
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

    # --- API Key / Session Cookie check ---
    auth_header = request.headers.get("Authorization", "")
    api_key_header = request.headers.get("X-API-Key", "")

    token = ""
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif api_key_header:
        token = api_key_header.strip()
    else:
        cookie_token = request.cookies.get("pv2_session", "").strip()
        if cookie_token:
            token = cookie_token

    if token not in cfg.auth.keys:
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
