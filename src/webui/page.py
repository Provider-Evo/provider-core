from __future__ import annotations

"""内置 WebUI 页面入口（向后兼容）。"""

from pathlib import Path

__all__ = ["render_webui"]

_STATIC_DIR = Path(__file__).parent / "static"


def render_webui(page: str = "webui") -> str:
    """渲染管理页面或在线文档页面（返回静态 HTML）。

    Args:
        page: 页面模式，支持 webui 或 docs。

    Returns:
        完整 HTML。
    """
    html_file = _STATIC_DIR / ("docs.html" if page == "docs" else "index.html")
    if html_file.exists():
        return html_file.read_text(encoding="utf-8")
    return "<!doctype html><html><head><title>Not Found</title></head><body>Static files not found</body></html>"
