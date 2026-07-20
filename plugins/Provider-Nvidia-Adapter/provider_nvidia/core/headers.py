


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

# =======================================================================
# 重导出 — 同包内协同模块的公共符号（保持外部 ``from .. import`` 路径稳定）
# =======================================================================

from .payload import (
    build_payload,
)

from .helpers.sse import (
    parse_sse_line,
)

__all__ = [
    "build_payload",
    "parse_sse_line",
]
