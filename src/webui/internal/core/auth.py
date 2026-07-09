"""WebUI cookie helpers — set, clear, and verify HttpOnly session cookies."""

from __future__ import annotations

import aiohttp.web

from src.webui.internal.core.security import token_manager

__all__ = [
    "COOKIE_NAME",
    "set_session_cookie",
    "clear_session_cookie",
    "verify_session_cookie",
]

COOKIE_NAME = "pv2_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


def set_session_cookie(resp: aiohttp.web.Response, token: str) -> None:
    """中文说明：set_session_cookie。

Set the HttpOnly session cookie on *resp*."""
    resp.set_cookie(
        COOKIE_NAME,
        token,
        path="/",
        httponly=True,
        samesite="Lax",
        max_age=COOKIE_MAX_AGE,
    )


def clear_session_cookie(resp: aiohttp.web.Response) -> None:
    """中文说明：clear_session_cookie。

Delete the session cookie."""
    resp.del_cookie(COOKIE_NAME, path="/")


def verify_session_cookie(request: aiohttp.web.Request) -> bool:
    """中文说明：verify_session_cookie。

Return True if the request carries a valid session cookie."""
    cookie_val = request.cookies.get(COOKIE_NAME, "")
    return token_manager.verify(cookie_val)
