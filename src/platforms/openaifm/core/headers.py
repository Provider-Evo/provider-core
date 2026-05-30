from __future__ import annotations

"""openaifm HTTP 请求头构建。"""

from typing import Dict


def build_headers(api_key: str) -> Dict[str, str]:
    """构建 HTTP 请求头。

    Args:
        api_key: API 密钥。

    Returns:
        请求头字典。
    """
    return {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": "Bearer {}".format(api_key) if api_key else "",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }
