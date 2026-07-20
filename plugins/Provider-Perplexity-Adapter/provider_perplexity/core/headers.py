

from typing import Dict

from .consts import BASE_URL


def build_headers(
    token: str = "",
    referer: str | None = None,
    request_id: str | None = None,
) -> Dict[str, str]:
    """Build Perplexity HTTP request headers.

    Args:
        token: Bearer token (empty string for public access).
        referer: Referer header value.
        request_id: X-Request-ID header value.

    Returns:
        Dictionary of HTTP headers.
    """
    headers: Dict[str, str] = {
        "accept": "text/event-stream",
        "accept-language": "en-US,en;q=0.9",
        "cache-control": "no-cache",
        "content-type": "application/json",
        "origin": BASE_URL,
        "user-agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
        ),
    }
    if referer:
        headers["referer"] = referer
    if request_id:
        headers["x-request-id"] = request_id
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers

# =======================================================================
# 重导出 — 同包内协同模块的公共符号（保持外部 ``from .. import`` 路径稳定）
# =======================================================================

from .payload import (
    build_payload,
)

__all__ = [
    "build_payload",
]
