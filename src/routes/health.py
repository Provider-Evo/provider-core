"""健康检查路由。"""

from __future__ import annotations

import aiohttp.web

__all__ = ["setup_routes"]


async def _health_check(request: aiohttp.web.Request) -> aiohttp.web.Response:
    return aiohttp.web.json_response({"status": "ok", "version": "2.0.4"})


def setup_routes(app: aiohttp.web.Application) -> None:
    app.router.add_get("/health", _health_check)
