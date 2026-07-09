from __future__ import annotations

"""WebUI 路由注册。"""

from pathlib import Path

import aiohttp.web

from src.webui.routers import (
    autoupdate_apply, autoupdate_check, autoupdate_diff, autoupdate_get, autoupdate_put,
    bg_image_get, bg_image_upload,
    config_get, config_put, config_reload, export_summary,
    files_copy, files_delete, files_download, files_drives, files_list, files_mkdir, files_move,
    files_project_root, files_read, files_rename, files_search, files_upload, files_write,
    login_page, logout_page,
    chat_media_get, chat_media_put,
    logs_ws, persist_get, persist_put, reload_service, requests_list, requests_ws,
    stats_api, stats_reset, summary_api, system_status, terminal_sessions_api, terminal_ws, webui_page,
    plugins_config_get, plugins_config_put, plugins_install, plugins_list, plugins_status, plugins_toggle, plugins_uninstall, plugins_update,
)
from src.webui.routers.admin import auth_regenerate, auth_update, auth_verify

__all__ = ["setup_routes"]


def _register_static_routes(app: aiohttp.web.Application) -> None:
    static_dir = Path(__file__).resolve().parent.parent / "static"
    app.router.add_static(
        "/static/", path=str(static_dir), name="webui_static",
        show_index=False, append_version=True,
    )
    prompts_dir = Path(__file__).resolve().parent.parent.parent / "prompts"
    if prompts_dir.is_dir():
        app.router.add_static(
            "/prompts/", path=str(prompts_dir), name="webui_prompts", show_index=False,
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
    app.router.add_post("/v1/admin/reload", reload_service)
    app.router.add_get("/v1/config", config_get)
    app.router.add_put("/v1/config", config_put)
    app.router.add_post("/v1/config/reload", config_reload)
    app.router.add_get("/v1/admin/autoupdate", autoupdate_get)
    app.router.add_put("/v1/admin/autoupdate", autoupdate_put)
    app.router.add_post("/v1/admin/autoupdate/check", autoupdate_check)
    app.router.add_post("/v1/admin/autoupdate/diff", autoupdate_diff)
    app.router.add_post("/v1/admin/autoupdate/apply", autoupdate_apply)
    # 插件管理路由
    app.router.add_get("/v1/admin/plugins", plugins_list)
    app.router.add_get("/v1/admin/plugins/status", plugins_status)
    app.router.add_post("/v1/admin/plugins/install", plugins_install)
    app.router.add_post("/v1/admin/plugins/uninstall", plugins_uninstall)
    app.router.add_post("/v1/admin/plugins/update", plugins_update)
    app.router.add_post("/v1/admin/plugins/toggle", plugins_toggle)
    app.router.add_post("/v1/admin/plugins/toggle/{plugin_id}", plugins_toggle)
    app.router.add_get("/v1/admin/plugins/config/{plugin_id}", plugins_config_get)
    app.router.add_put("/v1/admin/plugins/config/{plugin_id}", plugins_config_put)


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


def setup_routes(app: aiohttp.web.Application) -> None:
    """注册 WebUI 路由。"""
    _register_static_routes(app)
    _register_page_routes(app)
    _register_admin_routes(app)
    app.router.add_get("/v1/webui/stats", stats_api)
    app.router.add_post("/v1/webui/stats/reset", stats_reset)
    app.router.add_get("/v1/webui/ws/requests", requests_ws)
    app.router.add_get("/v1/webui/requests", requests_list)
    app.router.add_get("/v1/webui/persist/{filename}", persist_get)
    app.router.add_post("/v1/webui/persist/{filename}", persist_put)
    app.router.add_post("/v1/webui/chat-media", chat_media_put)
    app.router.add_get("/v1/webui/chat-media/{id}", chat_media_get)
    app.router.add_get("/v1/webui/ws/terminal/{session_id}", terminal_ws)
    app.router.add_get("/v1/webui/terminal/sessions", terminal_sessions_api)
    _register_file_routes(app)
    app.router.add_post("/v1/webui/bg-image", bg_image_upload)
    app.router.add_get("/v1/webui/bg-image/{filename}", bg_image_get)
    app.router.add_post("/v1/webui/auth/verify", auth_verify)
    app.router.add_post("/v1/webui/auth/update", auth_update)
    app.router.add_post("/v1/webui/auth/regenerate", auth_regenerate)
