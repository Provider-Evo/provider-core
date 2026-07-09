from __future__ import annotations

"""aiohttp middleware: CORS, authentication, error handling."""

from typing import Any

import aiohttp.web

from echotools.web.utils import cors_middleware, error_middleware, json_response

from src.core.config import get_config
from src.core.errors import AuthError, RateLimitError

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
    - ``/login``, ``/logout``, ``/static/``, ``/health`` pass unconditionally
    - OPTIONS requests pass unconditionally (CORS preflight)
    - All requests pass when auth is not enabled or no API keys are configured

    Auth flow (when auth.enabled=true and keys are configured):
    1. Check Group whitelist/blacklist (``X-Group-Id`` header) on ``/v1/`` routes
    2. Accept API Key (``Authorization: Bearer xxx`` or ``X-API-Key``)
       or WebUI session cookie (``pv2_session``)
    3. Protected routes: ``/`` and ``/v1/*`` except ``/v1/webui/*``
    4. Invalid credentials:
       - Browser page (``/`` or ``Accept: text/html``): 302 redirect to ``/login``
       - API client: JSON 401
    """
    path = request.path

    skip = {"/login", "/logout", "/health"}
    if path in skip or request.method == "OPTIONS":
        return await handler(request)
    if path.startswith("/static/"):
        return await handler(request)

    cfg = get_config()
    if not cfg.auth.enabled:
        return await handler(request)

    if not cfg.auth.keys:
        return await handler(request)

    # --- Group whitelist/blacklist check (API routes only) ---
    if path.startswith("/v1/") and not path.startswith("/v1/webui/"):
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

    if _has_valid_credentials(request, cfg):
        return await handler(request)

    # WebUI panel and OpenAI-compatible API routes require credentials.
    needs_auth = path == "/" or (
        path.startswith("/v1/") and not path.startswith("/v1/webui/")
    )
    if not needs_auth:
        return await handler(request)

    accept = request.headers.get("Accept", "")
    if path == "/" or "text/html" in accept:
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


def _has_valid_credentials(request: aiohttp.web.Request, cfg: Any) -> bool:
    """Return True when the request carries a valid API key or WebUI session."""
    auth_header = request.headers.get("Authorization", "")
    api_key_header = request.headers.get("X-API-Key", "")

    token = ""
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif api_key_header:
        token = api_key_header.strip()

    if token and token in cfg.auth.keys:
        return True

    from src.core.server.auth import COOKIE_NAME, verify_session_token

    cookie_val = request.cookies.get(COOKIE_NAME, "")
    return verify_session_token(cookie_val)


_error = error_middleware(
    error_map={
        AuthError: (401, "authentication_error"),
        RateLimitError: (429, "rate_limit_error"),
    },
)
