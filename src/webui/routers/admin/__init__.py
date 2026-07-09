from __future__ import annotations

"""管理类 WebUI 路由导出。"""

from .admin import bg_image_get, bg_image_upload, config_get, config_put, config_reload, persist_get, persist_put, reload_service
from .system import system_status
from .admin_auth import auth_regenerate, auth_update, auth_verify
from .autoupdate import autoupdate_apply, autoupdate_check, autoupdate_diff, autoupdate_get, autoupdate_put
from .plugins import (
    plugins_config_get,
    plugins_config_put,
    plugins_install,
    plugins_list,
    plugins_status,
    plugins_toggle,
    plugins_uninstall,
    plugins_update,
)

__all__ = [
    "auth_regenerate",
    "auth_update",
    "auth_verify",
    "autoupdate_apply",
    "autoupdate_check",
    "autoupdate_diff",
    "autoupdate_get",
    "autoupdate_put",
    "bg_image_get",
    "bg_image_upload",
    "config_get",
    "config_put",
    "config_reload",
    "persist_get",
    "persist_put",
    "plugins_config_get",
    "plugins_config_put",
    "plugins_install",
    "plugins_list",
    "plugins_status",
    "plugins_toggle",
    "plugins_uninstall",
    "plugins_update",
    "reload_service",
    "system_status",
]
