"""WebUI 管理端路由注册。"""

from __future__ import annotations

import aiohttp.web

from src.webui.routers import (
    autoupdate_apply,
    autoupdate_check,
    autoupdate_diff,
    autoupdate_get,
    autoupdate_put,
    config_get,
    config_put,
    config_raw_get,
    config_raw_put,
    config_reload,
    config_schema_get,
    plugins_config_bundle,
    plugins_config_get,
    plugins_config_put,
    plugins_config_reset,
    plugins_fetch_raw,
    plugins_git_status,
    plugins_host_version,
    plugins_icon,
    plugins_install,
    plugins_installed,
    plugins_list,
    plugins_local_changelog,
    plugins_local_readme,
    plugins_market_config,
    plugins_mirror_create,
    plugins_mirror_delete,
    plugins_mirror_list,
    plugins_mirror_update,
    plugins_progress,
    plugins_reload,
    plugins_runtime_components,
    plugins_runtime_home_cards,
    plugins_runtime_hook_specs,
    plugins_runtime_hooks,
    plugins_stats_proxy_summary,
    plugins_stats_proxy_toggle_like,
    plugins_status,
    plugins_toggle,
    plugins_uninstall,
    plugins_update,
    reload_service,
    webui_config_get,
    webui_config_put,
    webui_config_raw_get,
    webui_config_raw_put,
    webui_config_reload,
    webui_config_schema_get,
)
from src.webui.routers.admin.keys import (
    virtual_keys_create,
    virtual_keys_delete,
    virtual_keys_list,
)


def _register_admin_config_routes(app: aiohttp.web.Application) -> None:
    app.router.add_post("/v1/admin/reload", reload_service)
    app.router.add_get("/v1/config", config_get)
    app.router.add_put("/v1/config", config_put)
    app.router.add_post("/v1/config/reload", config_reload)
    app.router.add_get("/v1/config/raw", config_raw_get)
    app.router.add_post("/v1/config/raw", config_raw_put)
    app.router.add_get("/v1/admin/config/schema", config_schema_get)
    app.router.add_get("/v1/webui/config", webui_config_get)
    app.router.add_put("/v1/webui/config", webui_config_put)
    app.router.add_post("/v1/webui/config/reload", webui_config_reload)
    app.router.add_get("/v1/webui/config/raw", webui_config_raw_get)
    app.router.add_post("/v1/webui/config/raw", webui_config_raw_put)
    app.router.add_get("/v1/admin/webui/config/schema", webui_config_schema_get)
    app.router.add_get("/v1/admin/autoupdate", autoupdate_get)
    app.router.add_put("/v1/admin/autoupdate", autoupdate_put)
    app.router.add_post("/v1/admin/autoupdate/check", autoupdate_check)
    app.router.add_post("/v1/admin/autoupdate/diff", autoupdate_diff)
    app.router.add_post("/v1/admin/autoupdate/apply", autoupdate_apply)


def _register_admin_plugin_core_routes(app: aiohttp.web.Application) -> None:
    app.router.add_get("/v1/admin/plugins", plugins_list)
    app.router.add_get("/v1/admin/plugins/installed", plugins_installed)
    app.router.add_get("/v1/admin/plugins/status", plugins_status)
    app.router.add_get("/v1/admin/plugins/version", plugins_host_version)
    app.router.add_get("/v1/admin/plugins/git-status", plugins_git_status)
    app.router.add_get("/v1/admin/plugins/market-config", plugins_market_config)
    app.router.add_get("/v1/admin/plugins/progress", plugins_progress)
    app.router.add_post("/v1/admin/plugins/fetch-raw", plugins_fetch_raw)
    app.router.add_post("/v1/admin/plugins/reload", plugins_reload)
    app.router.add_post("/v1/admin/plugins/install", plugins_install)
    app.router.add_post("/v1/admin/plugins/uninstall", plugins_uninstall)
    app.router.add_post("/v1/admin/plugins/update", plugins_update)
    app.router.add_post("/v1/admin/plugins/toggle", plugins_toggle)
    app.router.add_post("/v1/admin/plugins/toggle/{plugin_id}", plugins_toggle)
    app.router.add_get("/v1/admin/plugins/config/{plugin_id}", plugins_config_get)
    app.router.add_get(
        "/v1/admin/plugins/config/{plugin_id}/bundle", plugins_config_bundle
    )
    app.router.add_put("/v1/admin/plugins/config/{plugin_id}", plugins_config_put)
    app.router.add_post(
        "/v1/admin/plugins/config/{plugin_id}/reset", plugins_config_reset
    )
    app.router.add_get(
        "/v1/admin/plugins/local-readme/{plugin_id}", plugins_local_readme
    )
    app.router.add_get(
        "/v1/admin/plugins/local-changelog/{plugin_id}", plugins_local_changelog
    )
    app.router.add_get("/v1/admin/plugins/icon/{plugin_id}", plugins_icon)


def _register_admin_plugin_extra_routes(app: aiohttp.web.Application) -> None:
    app.router.add_get("/v1/admin/plugins/mirrors", plugins_mirror_list)
    app.router.add_post("/v1/admin/plugins/mirrors", plugins_mirror_create)
    app.router.add_put("/v1/admin/plugins/mirrors/{mirror_id}", plugins_mirror_update)
    app.router.add_delete(
        "/v1/admin/plugins/mirrors/{mirror_id}", plugins_mirror_delete
    )
    app.router.add_get(
        "/v1/admin/plugins/runtime/components", plugins_runtime_home_cards
    )
    app.router.add_get(
        "/v1/admin/plugins/runtime/components/{plugin_id}", plugins_runtime_components
    )
    app.router.add_get("/v1/admin/plugins/runtime/hooks", plugins_runtime_hooks)
    app.router.add_get(
        "/v1/admin/plugins/runtime/hook-specs", plugins_runtime_hook_specs
    )
    app.router.add_get(
        "/v1/admin/plugins/stats/{plugin_id}", plugins_stats_proxy_summary
    )
    app.router.add_post(
        "/v1/admin/plugins/stats/{plugin_id}/like", plugins_stats_proxy_toggle_like
    )


def _register_admin_plugin_routes(app: aiohttp.web.Application) -> None:
    _register_admin_plugin_core_routes(app)
    _register_admin_plugin_extra_routes(app)


def register_admin_routes(app: aiohttp.web.Application) -> None:
    _register_admin_config_routes(app)
    _register_admin_plugin_routes(app)
    app.router.add_get("/v1/admin/keys", virtual_keys_list)
    app.router.add_post("/v1/admin/keys", virtual_keys_create)
    app.router.add_delete("/v1/admin/keys/{key_id}", virtual_keys_delete)
