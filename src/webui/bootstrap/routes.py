
from pathlib import Path

import aiohttp.web

from src.foundation.paths import resolve_project_root
from src.webui.bootstrap.routes_admin import register_admin_routes
from src.webui.routers import (
    autoupdate_apply,
    autoupdate_check,
    autoupdate_diff,
    autoupdate_get,
    autoupdate_put,
    bg_image_get,
    bg_image_upload,
    chat_media_get,
    chat_media_put,
    config_get,
    config_put,
    config_raw_get,
    config_raw_put,
    config_reload,
    config_schema_get,
    export_summary,
    files_copy,
    files_delete,
    files_download,
    files_drives,
    files_list,
    files_mkdir,
    files_move,
    files_project_root,
    files_read,
    files_rename,
    files_search,
    files_upload,
    files_write,
    login_page,
    logout_page,
    logs_ws,
    persist_get,
    persist_put,
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
    requests_list,
    requests_ws,
    stats_api,
    stats_reset,
    stats_ws,
    summary_api,
    system_status,
    terminal_audit_api,
    terminal_audit_config_api,
    terminal_audit_detail_api,
    terminal_commands_api,
    terminal_commands_export_api,
    terminal_commands_import_api,
    terminal_sessions_api,
    terminal_ssh_connections_api,
    terminal_ws,
    webui_config_get,
    webui_config_put,
    webui_config_raw_get,
    webui_config_raw_put,
    webui_config_reload,
    webui_config_schema_get,
    webui_page,
)
from src.webui.routers.admin import auth_regenerate, auth_update, auth_verify

__all__ = ["setup_routes"]


def _register_static_routes(app: aiohttp.web.Application) -> None:
    static_dir = Path(__file__).resolve().parent.parent / "frontend_media"
    app.router.add_static(
        "/static/",
        path=str(static_dir),
        name="webui_static",
        show_index=False,
        append_version=True,
    )
    prompts_dir = resolve_project_root() / "prompts"
    if prompts_dir.is_dir():
        app.router.add_static(
            "/prompts/",
            path=str(prompts_dir),
            name="webui_prompts",
            show_index=False,
        )


def _register_page_routes(app: aiohttp.web.Application) -> None:
    app.router.add_get("/", webui_page)
    app.router.add_route("*", "/login", login_page)
    app.router.add_get("/logout", logout_page)
    app.router.add_get("/v1/webui/summary", summary_api)
    app.router.add_get("/v1/webui/export", export_summary)
    app.router.add_get("/v1/webui/ws/logs", logs_ws)
    app.router.add_get("/v1/webui/system/status", system_status)


def _register_admin_routes(app: aiohttp.web.Application) -> None:
    register_admin_routes(app)


def _register_file_routes(app: aiohttp.web.Application) -> None:
    app.router.add_get("/v1/webui/files/list", files_list)
    app.router.add_get("/v1/webui/files/read", files_read)
    app.router.add_get("/v1/webui/files/download", files_download)
    app.router.add_post("/v1/webui/files/mkdir", files_mkdir)
    app.router.add_post("/v1/webui/files/delete", files_delete)
    app.router.add_post("/v1/webui/files/rename", files_rename)
    app.router.add_post("/v1/webui/files/write", files_write)
    app.router.add_post("/v1/webui/files/upload", files_upload)
    app.router.add_post("/v1/webui/files/copy", files_copy)
    app.router.add_post("/v1/webui/files/move", files_move)
    app.router.add_get("/v1/webui/files/search", files_search)
    app.router.add_get("/v1/webui/files/drives", files_drives)
    app.router.add_get("/v1/webui/files/project-root", files_project_root)


def _register_terminal_routes(app: aiohttp.web.Application) -> None:
    app.router.add_get("/v1/webui/ws/terminal/{session_id}", terminal_ws)
    app.router.add_get("/v1/webui/terminal/sessions", terminal_sessions_api)
    app.router.add_route(
        "*",
        "/v1/webui/terminal/ssh-connections",
        terminal_ssh_connections_api,
        name="terminal_ssh_connections",
    )
    app.router.add_route(
        "DELETE",
        "/v1/webui/terminal/ssh-connections/{connection_id}",
        terminal_ssh_connections_api,
        name="terminal_ssh_connection_delete",
    )
    app.router.add_get("/v1/webui/terminal/audit", terminal_audit_api)
    app.router.add_route(
        "*",
        "/v1/webui/terminal/audit/config",
        terminal_audit_config_api,
        name="terminal_audit_config",
    )
    app.router.add_route(
        "*",
        "/v1/webui/terminal/audit/{session_id}",
        terminal_audit_detail_api,
        name="terminal_audit_detail",
    )
    app.router.add_route(
        "*",
        "/v1/webui/terminal/commands",
        terminal_commands_api,
        name="terminal_commands",
    )
    app.router.add_route(
        "DELETE",
        "/v1/webui/terminal/commands/{command_id}",
        terminal_commands_api,
        name="terminal_command_delete",
    )
    app.router.add_get(
        "/v1/webui/terminal/commands/export", terminal_commands_export_api
    )
    app.router.add_post(
        "/v1/webui/terminal/commands/import", terminal_commands_import_api
    )


def _register_stats_persist_routes(app: aiohttp.web.Application) -> None:
    app.router.add_get("/v1/webui/stats", stats_api)
    app.router.add_post("/v1/webui/stats/reset", stats_reset)
    app.router.add_get("/v1/webui/ws/stats", stats_ws)
    app.router.add_get("/v1/webui/ws/requests", requests_ws)
    app.router.add_get("/v1/webui/requests", requests_list)
    app.router.add_get("/v1/webui/persist/{filename}", persist_get)
    app.router.add_post("/v1/webui/persist/{filename}", persist_put)
    app.router.add_post("/v1/webui/chat-media", chat_media_put)
    app.router.add_get("/v1/webui/chat-media/{id}", chat_media_get)


def _register_bgimage_auth_routes(app: aiohttp.web.Application) -> None:
    app.router.add_post("/v1/webui/bg-image", bg_image_upload)
    app.router.add_get("/v1/webui/bg-image/{filename}", bg_image_get)
    app.router.add_post("/v1/webui/auth/verify", auth_verify)
    app.router.add_post("/v1/webui/auth/update", auth_update)
    app.router.add_post("/v1/webui/auth/regenerate", auth_regenerate)


def setup_routes(app: aiohttp.web.Application) -> None:
    """注册 WebUI 路由。"""
    _register_static_routes(app)
    _register_page_routes(app)
    _register_admin_routes(app)
    _register_stats_persist_routes(app)
    _register_terminal_routes(app)
    _register_file_routes(app)
    _register_bgimage_auth_routes(app)
