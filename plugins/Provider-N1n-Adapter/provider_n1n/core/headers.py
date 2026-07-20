


from __future__ import annotations

from typing import Dict


def build_headers(token: str = "") -> Dict[str, str]:
    """构建请求头。

    Args:
        token: API Key，用于Authorization头。

    Returns:
        请求头字典。
    """
    headers: Dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN",
        "Cache-Control": "no-store",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/148.0.0.0 Safari/537.36"
        ),
    }
    if token:
        headers["Authorization"] = "Bearer {}".format(token)
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
