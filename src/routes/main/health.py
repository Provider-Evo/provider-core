
from __future__ import annotations

import aiohttp.web

from src.foundation.config import get_config

__all__ = ["setup_routes"]


async def _health_check(request: aiohttp.web.Request) -> aiohttp.web.Response:
    cfg = get_config()
    return aiohttp.web.json_response({"status": "ok", "version": cfg.server.version})


def setup_routes(app: aiohttp.web.Application) -> None:
    app.router.add_get("/health", _health_check)
