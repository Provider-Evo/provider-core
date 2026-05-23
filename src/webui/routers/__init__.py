from __future__ import annotations

"""WebUI routers 导出。"""

from .admin import config_get, config_put, config_reload, reload_service
from .docs import docs_page
from .pages import root_page, webui_page
from .summary import export_summary, summary_api
from .websocket import logs_ws

__all__ = [
    "config_get", "config_put", "config_reload", "reload_service",
    "docs_page", "root_page", "webui_page", "summary_api", "export_summary", "logs_ws",
]
