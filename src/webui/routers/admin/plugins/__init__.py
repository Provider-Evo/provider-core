from __future__ import annotations

from .plugin_catalog import (
    plugins_fetch_raw,
    plugins_git_status,
    plugins_host_version,
    plugins_icon,
    plugins_local_changelog,
    plugins_local_readme,
    plugins_market_config,
)
from .plugin_prog import plugins_progress
from .plugins import (
    plugins_config_bundle,
    plugins_config_get,
    plugins_config_put,
    plugins_config_reset,
    plugins_install,
    plugins_installed,
    plugins_list,
    plugins_reload,
    plugins_status,
    plugins_toggle,
    plugins_uninstall,
    plugins_update,
)
from .runtime.mirrors import (
    plugins_mirror_create,
    plugins_mirror_delete,
    plugins_mirror_list,
    plugins_mirror_update,
)
from .runtime.runtime_routes import (
    plugins_runtime_components,
    plugins_runtime_home_cards,
    plugins_runtime_hook_specs,
    plugins_runtime_hooks,
)
from .runtime.stats_proxy import (
    plugins_stats_proxy_summary,
    plugins_stats_proxy_toggle_like,
)

__all__ = [
    "plugins_config_bundle",
    "plugins_config_get",
    "plugins_config_put",
    "plugins_config_reset",
    "plugins_fetch_raw",
    "plugins_git_status",
    "plugins_host_version",
    "plugins_icon",
    "plugins_install",
    "plugins_installed",
    "plugins_list",
    "plugins_local_changelog",
    "plugins_local_readme",
    "plugins_market_config",
    "plugins_mirror_create",
    "plugins_mirror_delete",
    "plugins_mirror_list",
    "plugins_mirror_update",
    "plugins_progress",
    "plugins_reload",
    "plugins_runtime_components",
    "plugins_runtime_home_cards",
    "plugins_runtime_hook_specs",
    "plugins_runtime_hooks",
    "plugins_stats_proxy_summary",
    "plugins_stats_proxy_toggle_like",
    "plugins_status",
    "plugins_toggle",
    "plugins_uninstall",
    "plugins_update",
]
