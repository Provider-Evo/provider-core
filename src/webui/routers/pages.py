from __future__ import annotations

"""WebUI 页面路由。"""

import aiohttp.web

from src.webui.page import render_webui

__all__ = ["root_page", "webui_page"]


async def root_page(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """管理台页面。"""
    return aiohttp.web.Response(text=render_webui(page="webui"), content_type="text/html")


async def webui_page(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """在线文档页面。"""
    return aiohttp.web.Response(text=render_webui(page="docs"), content_type="text/html")
