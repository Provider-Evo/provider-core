


from typing import Dict


def build_headers(token: str = "") -> Dict[str, str]:
    """构建 gTTS 请求头。

    Args:
        token: 占位 token（gTTS 不需要）。

    Returns:
        请求头字典。
    """
    headers: Dict[str, str] = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://translate.google.com/",
    }
    if token:
        headers["Authorization"] = token
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
