from __future__ import annotations

"""aiohttp middleware: CORS, authentication, error handling."""

from typing import Any

import aiohttp.web
from echotools.web.utils import cors_middleware, error_middleware, json_response

from src.core.server.http.request_context import clear_api_token, set_api_token
from src.core.server.plugins.hook_reg import get_hook_registry
from src.core.utils.errors import AuthError, RateLimitError
from src.foundation.config import get_config

__all__ = ["_cors", "_auth_middleware", "_error"]

_cors = cors_middleware(
    allow_headers=(
        "Content-Type, Authorization, X-API-Key, " "Anthropic-Version, x-api-key"
    ),
)


_API_AUTH_EXEMPT_PREFIXES: tuple[str, ...] = ("/v1/coplan/",)


def _is_provider_api_auth_exempt(path: str) -> bool:
    """Routes under these prefixes use plugin-local auth, not provider API keys."""
    return any(path.startswith(prefix) for prefix in _API_AUTH_EXEMPT_PREFIXES)


def _is_webui_route(path: str) -> bool:
    """Return True if the path is a WebUI route that requires cookie auth."""
    return path.startswith("/v1/webui/")


async def _check_rate_limit(
    request: aiohttp.web.Request,
    cfg: Any,
    token: str,
    client_ip: str,
) -> aiohttp.web.StreamResponse | None:
    """Return a 429 response when the request exceeds the rate limit, else None."""
    path = request.path
    if not (cfg.rate_limit.enabled and _is_rate_limited_path(path)):
        return None

    from src.core.server.http.rate_limit import get_rate_limiter

    ok, retry = get_rate_limiter().check_request(token or "anon", client_ip)
    if ok:
        return None
    return json_response(
        {
            "error": {
                "message": "Rate limit exceeded",
                "type": "rate_limit_error",
                "code": "rate_limit_exceeded",
            }
        },
        status=429,
        headers={"Retry-After": str(retry)},
    )


def _check_group_access(
    request: aiohttp.web.Request,
    path: str,
    cfg: Any,
) -> aiohttp.web.StreamResponse | None:
    """Return a 401 response when the request's group is blocked, else None."""
    if not (path.startswith("/v1/") and not _is_provider_api_auth_exempt(path)):
        return None

    group_id = request.headers.get("X-Group-Id", "").strip()
    if not group_id:
        return None

    group_list_set = cfg.auth.group_list_set
    group_list_type = cfg.auth.group_list_type.lower().strip()

    if group_list_type == "blacklist" and group_id in group_list_set:
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
    if group_list_type == "whitelist" and group_id not in group_list_set:
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
    return None


async def _handle_webui_auth(
    request: aiohttp.web.Request,
    cfg: Any,
    handler: Any,
) -> aiohttp.web.StreamResponse:
    """Handle auth for ``/v1/webui/*`` routes: cookie auth, 401 JSON on failure."""
    if await _validate_webui_session(request, cfg):
        return await handler(request)
    return json_response(
        {
            "error": {
                "message": "Unauthorized",
                "type": "auth_error",
            }
        },
        status=401,
    )


async def _handle_protected_route_auth(
    request: aiohttp.web.Request,
    path: str,
    cfg: Any,
    handler: Any,
) -> aiohttp.web.StreamResponse:
    """Handle auth for the remaining protected routes (API key / session cookie)."""
    if await _validate_credentials(request, cfg):
        return await handler(request)

    # Coplan routes use plugin-local auth, skip further checks
    if _is_provider_api_auth_exempt(path):
        return await handler(request)

    # Root page or API routes require auth
    needs_auth = path == "/" or path.startswith("/v1/")
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
    3. Protected routes: ``/`` and ``/v1/*`` except ``/v1/webui/*`` and ``/v1/coplan/*``
    4. Invalid credentials:
       - Browser page (``/`` or ``Accept: text/html``): 302 redirect to ``/login``
       - API client: JSON 401
    """
    path = request.path

    skip = {"/login", "/logout", "/health", "/metrics"}
    if path in skip or request.method == "OPTIONS":
        return await handler(request)
    if path.startswith("/static/"):
        return await handler(request)

    cfg = get_config()
    token = _extract_bearer_token(request)
    client_ip = request.remote or "0.0.0.0"

    rate_limit_response = await _check_rate_limit(request, cfg, token, client_ip)
    if rate_limit_response is not None:
        return rate_limit_response

    clear_api_token()
    try:
        return await _run_auth_flow(request, path, cfg, token, handler)
    finally:
        clear_api_token()


async def _run_auth_flow(
    request: aiohttp.web.Request,
    path: str,
    cfg: Any,
    token: str,
    handler: Any,
) -> aiohttp.web.StreamResponse:
    """执行认证流程：白名单校验、凭据校验、路由分发。"""
    creds_required = (
        cfg.auth.enabled and bool(cfg.auth.keys)
    ) or cfg.virtual_keys.enabled

    # Auth disabled: allow all requests
    if not cfg.auth.enabled:
        return await handler(request)

    # No credentials configured: allow all requests
    if not creds_required:
        return await handler(request)

    if not cfg.auth.keys and not token and not cfg.virtual_keys.enabled:
        return await handler(request)

    group_response = _check_group_access(request, path, cfg)
    if group_response is not None:
        return group_response

    if _is_webui_route(path):
        return await _handle_webui_auth(request, cfg, handler)

    return await _handle_protected_route_auth(request, path, cfg, handler)


def _extract_bearer_token(request: aiohttp.web.Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    api_key_header = request.headers.get("X-API-Key", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    if api_key_header:
        return api_key_header.strip()
    return ""


def _is_rate_limited_path(path: str) -> bool:
    return path.startswith(("/v1/chat/", "/v1/completions", "/v1/messages"))


async def _validate_credentials(request: aiohttp.web.Request, cfg: Any) -> bool:
    """Return True when the request carries a valid API key or WebUI session."""
    token = _extract_bearer_token(request)
    if token and cfg.auth.keys and token in cfg.auth.keys:
        set_api_token(token)
        return True
    if token and cfg.virtual_keys.enabled:
        from src.core.auth.virtual_keys import get_virtual_key_store

        store = get_virtual_key_store()
        record = await store.authenticate(token)
        if record is not None:
            request["_virtual_key"] = record
            set_api_token(token)
            return True
    if token:
        hook_result = await get_hook_registry().invoke(
            "auth.credentials.validate",
            {"token": token},
        )
        if hook_result.context.get("valid"):
            set_api_token(token)
            return True

    from src.core.server.http.auth import COOKIE_NAME, verify_session_token

    cookie_val = request.cookies.get(COOKIE_NAME, "")
    return verify_session_token(cookie_val)


async def _validate_webui_session(request: aiohttp.web.Request, cfg: Any) -> bool:
    """Return True when the request carries a valid WebUI session cookie.

    WebUI routes require cookie-based authentication (pv2_session).
    If auth is disabled in config, all WebUI routes are public.
    """
    if not cfg.auth.enabled:
        return True

    from src.core.server.http.auth import COOKIE_NAME, verify_session_token

    cookie_val = request.cookies.get(COOKIE_NAME, "")
    return verify_session_token(cookie_val)


_error = error_middleware(
    error_map={
        AuthError: (401, "authentication_error"),
        RateLimitError: (429, "rate_limit_error"),
    },
)
