from __future__ import annotations

"""WebUI 静态资源禁缓存中间件。"""

from typing import Awaitable, Callable

import aiohttp.web

_Handler = Callable[[aiohttp.web.Request], Awaitable[aiohttp.web.StreamResponse]]


@aiohttp.web.middleware
async def static_nocache_middleware(
    request: aiohttp.web.Request,
    handler: _Handler,
) -> aiohttp.web.StreamResponse:
    """对 /static/ 路径的响应追加 no-cache 头，确保修改后浏览器立即获取新文件。"""
    response = await handler(request)
    if request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response
