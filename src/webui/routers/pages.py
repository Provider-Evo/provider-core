from __future__ import annotations

"""WebUI 页面路由。"""

from pathlib import Path

import aiohttp.web

__all__ = ["webui_page"]

STATIC_DIR = Path(__file__).parent.parent / "static"


async def webui_page(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """管理台页面。"""
    response = aiohttp.web.FileResponse(STATIC_DIR / "index.html")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response
