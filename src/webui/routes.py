from __future__ import annotations

"""WebUI 路由注册。"""

from pathlib import Path

import aiohttp.web

from src.webui.routers import (
    autoupdate_check, autoupdate_get, autoupdate_put,
    config_get, config_put, config_reload, docs_page, export_summary,
    logs_ws, reload_service, root_page, summary_api, webui_page,
)

__all__ = ["setup_routes"]


def setup_routes(app: aiohttp.web.Application) -> None:
    """注册 WebUI 路由。"""
    # 静态文件路由（开发模式禁用缓存，启用版本追加）
    static_dir = Path(__file__).parent / "static"
    app.router.add_static(
        "/webui/static/",
        path=str(static_dir),
        name="webui_static",
        show_index=False,
        append_version=True,
    )

    app.router.add_get("/webui", root_page)
    app.router.add_get("/docs", docs_page)
    app.router.add_get("/v1/webui/summary", summary_api)
    app.router.add_get("/v1/webui/export", export_summary)
    app.router.add_get("/v1/webui/ws/logs", logs_ws)
    # 管理端点
    app.router.add_post("/v1/admin/reload", reload_service)
    app.router.add_get("/v1/config", config_get)
    app.router.add_put("/v1/config", config_put)
    app.router.add_post("/v1/config/reload", config_reload)
    # 自动更新端点
    app.router.add_get("/v1/admin/autoupdate", autoupdate_get)
    app.router.add_put("/v1/admin/autoupdate", autoupdate_put)
    app.router.add_post("/v1/admin/autoupdate/check", autoupdate_check)
