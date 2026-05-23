from __future__ import annotations

"""内置 WebUI 页面入口。"""

from src.core.config import get_config
from src.webui.templates import render_document

__all__ = ["render_webui"]


def render_webui(page: str = "webui") -> str:
    """渲染管理页面或在线文档页面。

    Args:
        page: 页面模式，支持 webui 或 docs。

    Returns:
        完整 HTML。
    """
    config = get_config()
    initial_tab = "docs" if page == "docs" else "overview"
    return render_document(
        version=config.server.version,
        host=config.server.host,
        port=config.server.port,
        initial_tab=initial_tab,
    )
