from __future__ import annotations

from typing import Dict


def build_headers(proxy_addr: str = "") -> Dict[str, str]:
    """Build request headers.

    Args:
        proxy_addr: Proxy address (informational only, not used in headers).

    Returns:
        Header dictionary.
    """
    headers: Dict[str, str] = {
        "Content-Type": "application/json",
    }
    return headers
