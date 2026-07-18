"""static_nocache 模块 — WebUI 层。

职责：
    作为 Provider-Evo 项目标准模块，提供 static_nocache 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""



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
