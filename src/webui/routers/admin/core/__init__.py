from __future__ import annotations

"""管理端核心路由（会话、系统、自动更新）。"""

from .admin import bg_image_get, bg_image_upload, persist_get, persist_put, reload_service
from .admin_auth import auth_regenerate, auth_update, auth_verify
from .autoupdate import autoupdate_apply, autoupdate_check, autoupdate_diff, autoupdate_get, autoupdate_put
from .system import system_status

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
    "persist_get",
    "persist_put",
    "reload_service",
    "system_status",
]
