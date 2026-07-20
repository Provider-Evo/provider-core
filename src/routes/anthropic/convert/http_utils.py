
from typing import Any

import aiohttp.web

from src.core.server import json_response


def _json(data: Any, status: int = 200) -> aiohttp.web.Response:
    return json_response(data, status=status)


def _err(
    status: int,
    message: str,
    error_type: str = "server_error",
) -> aiohttp.web.Response:
    """构建 Anthropic 格式错误响应。

    Args:
        status: HTTP 状态码。
        message: 错误信息。
        error_type: Anthropic 错误类型字符串。

    Returns:
        Response 实例。
    """
    return _json(
        {
            "type": "error",
            "error": {"type": error_type, "message": message},
        },
        status=status,
    )
