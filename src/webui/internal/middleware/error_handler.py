"""error_handler 模块 — WebUI 层。

职责：
    作为 Provider-Evo 项目标准模块，提供 error_handler 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""

from typing import Awaitable, Callable

import aiohttp.web

from src.foundation.logger import get_logger

logger = get_logger(__name__)

_Handler = Callable[[aiohttp.web.Request], Awaitable[aiohttp.web.StreamResponse]]


@aiohttp.web.middleware
async def error_middleware(
    request: aiohttp.web.Request,
    handler: _Handler,
) -> aiohttp.web.StreamResponse:
    """统一处理 WebUI 路由异常。"""
    try:
        return await handler(request)
    except aiohttp.web.HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "WebUI 请求异常: %s %s -> %s",
            request.method,
            request.path,
            exc,
            exc_info=True,
        )
        return aiohttp.web.json_response(
            {"error": {"message": str(exc), "type": "webui_error"}},
            status=500,
        )
