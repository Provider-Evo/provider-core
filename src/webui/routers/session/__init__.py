from __future__ import annotations

"""会话与页面类 WebUI 路由导出。"""

from .chat_media import chat_media_get, chat_media_put
from .pages import login_page, logout_page, webui_page
from .terminal import (
    list_sessions,
    recover_sessions,
    terminal_audit_api,
    terminal_audit_config_api,
    terminal_audit_detail_api,
    terminal_commands_api,
    terminal_commands_export_api,
    terminal_commands_import_api,
    terminal_sessions_api,
    terminal_ssh_connections_api,
    terminal_ws,
)
from .wsock import logs_ws

__all__ = [
    "chat_media_get",
    "chat_media_put",
    "list_sessions",
    "login_page",
    "logout_page",
    "logs_ws",
    "recover_sessions",
    "terminal_audit_api",
    "terminal_audit_config_api",
    "terminal_audit_detail_api",
    "terminal_commands_api",
    "terminal_commands_export_api",
    "terminal_commands_import_api",
    "terminal_sessions_api",
    "terminal_ssh_connections_api",
    "terminal_ws",
    "webui_page",
]
