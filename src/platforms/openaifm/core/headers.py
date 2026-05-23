from __future__ import annotations

from typing import Dict


def build_headers(token: str = "") -> Dict[str, str]:
    """Build request headers for openaifm API calls.

    Args:
        token: Cookie or auth string.

    Returns:
        Header dictionary.

    Examples:
        >>> h = build_headers()
        >>> h["accept"]
        '*/*'
        >>> h2 = build_headers("mykey")
        >>> h2["Cookie"]
        'mykey'
    """
    headers: Dict[str, str] = {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "origin": "https://www.openai.fm",
        "referer": "https://www.openai.fm/worker-20260303-rate-limit.js",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
        ),
    }
    if token:
        headers["Cookie"] = token
    return headers
