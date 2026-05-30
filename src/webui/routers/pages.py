from __future__ import annotations

"""WebUI 页面路由。"""

from pathlib import Path

import aiohttp.web

__all__ = ["root_page", "webui_page"]

STATIC_DIR = Path(__file__).parent.parent / "static"


async def root_page(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """管理台页面。"""
    return aiohttp.web.FileResponse(STATIC_DIR / "index.html")


async def webui_page(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """在线文档页面。"""
    return aiohttp.web.FileResponse(STATIC_DIR / "docs.html")
