from __future__ import annotations

"""HTTP header builders aligned with the current Qwen web flow."""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from .crypto import get_baxia_tokens
from .endpoints import (
    APP_VERSION,
    BASE_URL,
    CHAT_ORIGIN,
    SEC_CH_UA,
    SEC_CH_UA_PLATFORM,
    USER_AGENT,
    WEB_VERSION,
)


def make_request_id() -> str:
    """Return a new request identifier."""
    return str(uuid.uuid4())


def make_timezone() -> str:
    """Return the browser-like timezone header value."""
    now = datetime.now().astimezone()
    offset = now.utcoffset()
    if offset is None:
        suffix = "+0000"
    else:
        total_seconds = int(offset.total_seconds())
        sign = "+" if total_seconds >= 0 else "-"
        total_seconds = abs(total_seconds)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        suffix = f"{sign}{hours:02d}{minutes:02d}"
    return now.strftime(f"%a %b %d %Y %H:%M:%S GMT{suffix}")


def build_cookie_string(cookies: Optional[Dict[str, Any]]) -> str:
    """Convert a cookie mapping into a request header string."""
    if not cookies:
        return ""
    return "; ".join(f"{key}={value}" for key, value in cookies.items() if value not in {None, ""})


def _base_headers() -> Dict[str, str]:
    return {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        "Origin": CHAT_ORIGIN,
        "Referer": f"{CHAT_ORIGIN}/",
        "Source": "web",
        "X-Request-Id": make_request_id(),
        "Timezone": make_timezone(),
        "Sec-Ch-Ua": SEC_CH_UA,
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": SEC_CH_UA_PLATFORM,
    }


def build_login_headers() -> Dict[str, str]:
    """Build headers for the v2 sign-in endpoint."""
    headers = _base_headers()
    headers["Version"] = APP_VERSION
    headers["x-request-origin"] = BASE_URL
    return headers


def build_headers(
    token: str,
    *,
    chat_id: str = "",
    include_sse: bool = False,
    include_version: bool = True,
    fingerprint: str = "",
    cookies: Optional[Dict[str, Any]] = None,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Build authenticated headers for Qwen chat APIs."""
    headers = _base_headers()
    headers["Authorization"] = f"Bearer {token}"
    baxia = get_baxia_tokens()
    headers["bx-v"] = baxia["bxV"]
    headers["bx-ua"] = baxia["bxUa"]
    headers["bx-umidtoken"] = baxia["bxUmidToken"]
    if include_version:
        headers["version"] = WEB_VERSION
    if chat_id:
        headers["Referer"] = f"{CHAT_ORIGIN}/c/{chat_id}"
    if include_sse:
        headers["X-Accel-Buffering"] = "no"
    cookie_string = build_cookie_string(cookies)
    if cookie_string:
        headers["Cookie"] = cookie_string
    if extra_headers:
        headers.update(extra_headers)
    return headers


def build_stop_headers(token: str) -> Dict[str, str]:
    """Build headers for the stop-generation endpoint."""
    return build_headers(token, include_version=False)
