from __future__ import annotations

"""配置面板路由。"""

from .config_panel import (
    config_get,
    config_put,
    config_reload,
    config_raw_get,
    config_raw_put,
    config_schema_get,
)
from .webui_config_panel import (
    webui_config_get,
    webui_config_put,
    webui_config_reload,
    webui_config_raw_get,
    webui_config_raw_put,
    webui_config_schema_get,
)

__all__ = [
    "config_get",
    "config_put",
    "config_reload",
    "config_raw_get",
    "config_raw_put",
    "config_schema_get",
    "webui_config_get",
    "webui_config_put",
    "webui_config_reload",
    "webui_config_raw_get",
    "webui_config_raw_put",
    "webui_config_schema_get",
]
