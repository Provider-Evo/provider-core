from __future__ import annotations

"""WebUI 路由注册。"""

from pathlib import Path

import aiohttp.web

from src.webui.routers import (
    autoupdate_check, autoupdate_get, autoupdate_put,
    config_get, config_put, config_reload, export_summary,
    login_page, logout_page,
    logs_ws, reload_service, summary_api, webui_page,
)

__all__ = ["setup_routes"]


def setup_routes(app: aiohttp.web.Application) -> None:
    """注册 WebUI 路由。"""
    static_dir = Path(__file__).parent / "static"
    app.router.add_static(
        "/static/",
        path=str(static_dir),
        name="webui_static",
        show_index=False,
        append_version=True,
    )

    app.router.add_get("/", webui_page)
    app.router.add_route("*", "/login", login_page)
    app.router.add_get("/logout", logout_page)
    app.router.add_get("/v1/webui/summary", summary_api)
    app.router.add_get("/v1/webui/export", export_summary)
    app.router.add_get("/v1/webui/ws/logs", logs_ws)
    app.router.add_post("/v1/admin/reload", reload_service)
    app.router.add_get("/v1/config", config_get)
    app.router.add_put("/v1/config", config_put)
    app.router.add_post("/v1/config/reload", config_reload)
    app.router.add_get("/v1/admin/autoupdate", autoupdate_get)
    app.router.add_put("/v1/admin/autoupdate", autoupdate_put)
    app.router.add_post("/v1/admin/autoupdate/check", autoupdate_check)
