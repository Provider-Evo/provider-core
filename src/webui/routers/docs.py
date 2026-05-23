from __future__ import annotations

"""WebUI 在线文档路由。"""

import aiohttp.web

from src.webui.page import render_webui

__all__ = ["docs_page"]


async def docs_page(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """文档页。"""
    return aiohttp.web.Response(text=render_webui(page="docs"), content_type="text/html")
