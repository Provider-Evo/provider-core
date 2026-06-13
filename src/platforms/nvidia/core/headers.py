from __future__ import annotations

"""Nvidia 请求头构造。"""

from typing import Any, Dict


def build_headers(api_key: str) -> Dict[str, str]:
    """构建请求头。

    Args:
        api_key: Nvidia API Key。

    Returns:
        请求头字典。

    Examples:
        >>> h = build_headers("test-key")
        >>> h["Authorization"]
        'Bearer test-key'
        >>> h["Content-Type"]
        'application/json'
    """
    return {
        "Authorization": "Bearer {}".format(api_key),
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
