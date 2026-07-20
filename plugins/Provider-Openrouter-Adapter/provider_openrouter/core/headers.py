

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

# =======================================================================
# 重导出 — 同包内协同模块的公共符号（保持外部 ``from .. import`` 路径稳定）
# =======================================================================

from .payload import (
    build_payload,
)

from .sse import (
    parse_sse_line,
)

__all__ = [
    "build_payload",
    "parse_sse_line",
]
