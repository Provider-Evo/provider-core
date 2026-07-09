from __future__ import annotations

from typing import Dict


def build_headers(api_key: str = "") -> Dict[str, str]:
    """构建请求头。

    Args:
        api_key: Zen API Key。

    Returns:
        请求头字典。
    """
    headers: Dict[str, str] = {
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = "Bearer {}".format(api_key)
    return headers
