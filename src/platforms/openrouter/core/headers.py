from __future__ import annotations

from typing import Dict

DEFAULT_HEADERS: Dict[str, str] = {
    "Content-Type": "application/json",
    "HTTP-Referer": "https://provider-v2.local",
    "X-Title": "Provider-V2",
}


def build_headers(api_key: str = "") -> Dict[str, str]:
    """构建请求头。

    Args:
        api_key: OpenRouter API Key。

    Returns:
        请求头字典。
    """
    headers: Dict[str, str] = dict(DEFAULT_HEADERS)
    if api_key:
        headers["Authorization"] = "Bearer {}".format(api_key)
    return headers
