from __future__ import annotations

"""WebUI 在线文档路由。"""

from pathlib import Path

import aiohttp.web

__all__ = ["docs_page"]

STATIC_DIR = Path(__file__).parent.parent / "static"


async def docs_page(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """文档页。"""
    return aiohttp.web.FileResponse(STATIC_DIR / "docs.html")
