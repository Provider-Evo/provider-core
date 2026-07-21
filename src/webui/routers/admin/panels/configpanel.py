"""Backward-compat alias for cfg_panel (webui config panel routes)."""
from __future__ import annotations

from src.foundation.paths import config_dir
from src.webui.routers.admin.panels.cfg_panel import *  # noqa: F403
from src.webui.routers.admin.panels.cfg_panel import (
    webui_config_get,
    webui_config_put,
    webui_config_raw_get,
    webui_config_raw_put,
    webui_config_reload,
    webui_config_schema_get,
)

__all__ = [
    "config_dir",
    "webui_config_get",
    "webui_config_put",
    "webui_config_reload",
    "webui_config_schema_get",
    "webui_config_raw_get",
    "webui_config_raw_put",
]
