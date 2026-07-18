"""插件管理 WebUI 子模块（对照 Provider-V2 src/webui/routers/plugin/）。"""
from __future__ import annotations

from .mirrors import (
    plugins_mirror_create,
    plugins_mirror_delete,
    plugins_mirror_list,
    plugins_mirror_update,
)
from .runtime_routes import (
    plugins_runtime_components,
    plugins_runtime_home_cards,
    plugins_runtime_hook_specs,
    plugins_runtime_hooks,
)
from .stats_proxy import plugins_stats_proxy_summary, plugins_stats_proxy_toggle_like

__all__ = [
    "plugins_mirror_create",
    "plugins_mirror_delete",
    "plugins_mirror_list",
    "plugins_mirror_update",
    "plugins_runtime_components",
    "plugins_runtime_home_cards",
    "plugins_runtime_hooks",
    "plugins_runtime_hook_specs",
    "plugins_stats_proxy_summary",
    "plugins_stats_proxy_toggle_like",
]
