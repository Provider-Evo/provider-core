from __future__ import annotations

"""WebUI 页面路由。"""

import re
from pathlib import Path

import aiohttp.web

__all__ = ["webui_page"]

STATIC_DIR = Path(__file__).parent.parent / "static"
_html_cache: dict = {}


def _read_html_with_versions() -> str:
    """读取 index.html 并为 /static/ 资源追加 mtime 版本号。"""
    html_path = STATIC_DIR / "index.html"

    all_mtimes = [html_path.stat().st_mtime]
    for ext in ("*.js", "*.css"):
        for f in STATIC_DIR.rglob(ext):
            all_mtimes.append(f.stat().st_mtime)
    max_mtime = max(all_mtimes)

    if _html_cache.get("max_mtime") == max_mtime:
        return _html_cache["html"]

    text = html_path.read_text(encoding="utf-8")

    def _add_version(match: re.Match) -> str:
        url = match.group(1)
        rel = url.lstrip("/")
        fpath = STATIC_DIR.parent / rel
        if fpath.is_file():
            ver = int(fpath.stat().st_mtime)
            return f'{match.group(0).split("?")[0]}?v={ver}"'
        return match.group(0)

    text = re.sub(
        r'(?:href|src)="(/static/[^"]+)"',
        _add_version,
        text,
    )
    _html_cache["max_mtime"] = max_mtime
    _html_cache["html"] = text
    return text


async def webui_page(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """管理台页面。"""
    html = _read_html_with_versions()
    response = aiohttp.web.Response(text=html, content_type="text/html")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response
