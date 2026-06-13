from __future__ import annotations

"""WebUI routers 导出。"""

from .admin import config_get, config_put, config_reload, reload_service
from .autoupdate import autoupdate_check, autoupdate_get, autoupdate_put
from .pages import login_page, logout_page, webui_page
from .summary import export_summary, summary_api
from .websocket import logs_ws

__all__ = [
    "config_get", "config_put", "config_reload", "reload_service",
    "autoupdate_get", "autoupdate_put", "autoupdate_check",
    "webui_page", "login_page", "logout_page",
    "summary_api", "export_summary", "logs_ws",
]
