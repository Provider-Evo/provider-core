from __future__ import annotations

"""WebUI routers 导出。"""

from .admin import config_get, config_put, config_reload, persist_get, persist_put, reload_service, bg_image_upload, bg_image_get
from .autoupdate import autoupdate_apply, autoupdate_check, autoupdate_diff, autoupdate_get, autoupdate_put
from .files import files_copy, files_delete, files_download, files_drives, files_list, files_mkdir, files_move, files_project_root, files_read, files_rename, files_search, files_upload, files_write
from .pages import login_page, logout_page, webui_page
from .stats import requests_list, requests_ws, stats_api, stats_reset
from .summary import export_summary, summary_api
from .terminal import list_sessions, recover_sessions, terminal_sessions_api, terminal_ws
from .websocket import logs_ws

__all__ = [
    "config_get", "config_put", "config_reload", "persist_get", "persist_put", "reload_service",
    "bg_image_upload", "bg_image_get",
    "autoupdate_get", "autoupdate_put", "autoupdate_check", "autoupdate_diff", "autoupdate_apply",
    "files_list", "files_read", "files_download", "files_mkdir", "files_delete", "files_rename", "files_write", "files_upload", "files_copy", "files_move", "files_search", "files_drives", "files_project_root",
    "webui_page", "login_page", "logout_page",
    "summary_api", "export_summary", "logs_ws",
    "stats_api", "stats_reset", "requests_ws", "requests_list",
    "terminal_ws", "terminal_sessions_api", "recover_sessions", "list_sessions",
]
