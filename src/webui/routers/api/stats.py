from __future__ import annotations

"""WebUI 统计路由 — 请求统计 + 系统资源 + 请求日志 WebSocket。"""

import asyncio
import os
import time

import aiohttp.web

from src.webui.services.stats import get_stats
from src.webui.services.request_log import request_broker

__all__ = ["stats_api", "stats_reset", "requests_ws", "requests_list"]


def _system_info() -> dict:
    """采集系统资源（轻量级，无第三方依赖）。"""
    info: dict = {
        "pid": os.getpid(),
        "cpu_count": os.cpu_count() or 0,
    }
    try:
        import resource as _res
        usage = _res.getrusage(_res.RUSAGE_SELF)
        info["memory_mb"] = round(usage.ru_maxrss / 1024, 1)
    except (ImportError, AttributeError):
        info["memory_mb"] = None
    try:
        load = os.getloadavg()
        info["load_avg"] = [round(x, 2) for x in load]
    except (OSError, AttributeError):
        info["load_avg"] = None
    return info


async def stats_api(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """请求统计 + 系统资源。"""
    stats = get_stats()
    payload = stats.snapshot()
    payload["system"] = _system_info()
    return aiohttp.web.json_response(payload)


async def stats_reset(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """重置统计。"""
    get_stats().reset()
    return aiohttp.web.json_response({"status": "ok"})


async def requests_ws(request: aiohttp.web.Request) -> aiohttp.web.WebSocketResponse:
    """WebSocket 端点：实时推送请求事件。"""
    ws = aiohttp.web.WebSocketResponse()
    await ws.prepare(request)

    # Save event loop for broker
    try:
        loop = asyncio.get_running_loop()
        request_broker.set_loop(loop)
    except Exception:
        pass

    await request_broker.register(ws)
    try:
        # Send hello + history
        await ws.send_json({"type": "hello"})
        count = await request_broker.send_history(ws)
        await ws.send_json({"type": "history", "count": count})

        # Keep connection alive
        async for msg in ws:
            if msg.type == aiohttp.web.WSMsgType.TEXT:
                if msg.data == "ping":
                    await ws.send_json({"type": "pong"})
            elif msg.type in (aiohttp.web.WSMsgType.ERROR, aiohttp.web.WSMsgType.CLOSE):
                break
    finally:
        await request_broker.unregister(ws)

    return ws


async def requests_list(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """REST API：返回最近请求列表。"""
    limit = int(request.query.get("limit", "50"))
    items = request_broker.get_recent(limit)
    return aiohttp.web.json_response({"requests": items})
