from __future__ import annotations

"""WebUI 管理端点：服务重载、配置读写。"""

import aiohttp.web

__all__ = ["reload_service", "config_get", "config_put", "config_reload"]


async def reload_service(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/admin/reload — 热重载 WebUI 应用。"""
    server = request.app.get("webui_server")
    if server is None:
        return aiohttp.web.json_response(
            {"error": "server not available"},
            status=503,
        )
    try:
        await server.reload_app()
        return aiohttp.web.json_response(
            {"status": "ok", "message": "WebUI reloaded"},
        )
    except Exception as exc:
        return aiohttp.web.json_response(
            {"error": str(exc)},
            status=500,
        )


async def config_get(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/config — 返回完整配置 JSON。"""
    from src.core.config import get_config

    cfg = get_config()
    return aiohttp.web.json_response(cfg.to_dict())


async def config_put(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """PUT /v1/config — 写入配置并重新加载。"""
    from src.core.config import write_config

    try:
        payload = await request.json()
    except Exception:
        return aiohttp.web.json_response(
            {"error": "invalid JSON body"},
            status=400,
        )

    ok = await write_config(payload)
    if ok:
        return aiohttp.web.json_response(
            {"status": "ok", "message": "Config saved and reloaded"},
        )
    return aiohttp.web.json_response(
        {"error": "write failed"},
        status=500,
    )


async def config_reload(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/config/reload — 从文件重新加载配置，丢弃未保存更改。"""
    from src.core.config import reload_config

    ok = await reload_config()
    if ok:
        return aiohttp.web.json_response(
            {"status": "ok", "message": "Config reloaded from file"},
        )
    return aiohttp.web.json_response(
        {"error": "reload failed"},
        status=500,
    )
