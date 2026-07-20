
import asyncio
import os
import time

import aiohttp.web

from src.webui.data.services.logs.request_log import clamp_query_limit, request_broker
from src.webui.data.services.stats import get_stats

__all__ = ["stats_api", "stats_reset", "requests_ws", "requests_list", "stats_ws"]

_STATS_PUSH_INTERVAL = 3.0


def _stats_snapshot() -> dict:
    """构建与 stats_api 相同的统计快照。"""
    stats = get_stats()
    payload = stats.snapshot()
    payload["system"] = _system_info()

    from src.core.dispatch.cache.response_cache import get_response_cache

    payload["cache"] = get_response_cache().stats()
    return payload


class _StatsBroker:
    """按固定间隔向所有已连接 WebSocket 推送统计快照。"""

    def __init__(self) -> None:
        self._sockets: set = set()
        self._lock = asyncio.Lock()
        self._loop_task = None

    async def register(self, ws: aiohttp.web.WebSocketResponse) -> None:
        async with self._lock:
            self._sockets.add(ws)
            if self._loop_task is None or self._loop_task.done():
                self._loop_task = asyncio.ensure_future(self._push_loop())

    async def unregister(self, ws: aiohttp.web.WebSocketResponse) -> None:
        async with self._lock:
            self._sockets.discard(ws)

    async def _push_loop(self) -> None:
        while True:
            await asyncio.sleep(_STATS_PUSH_INTERVAL)
            async with self._lock:
                if not self._sockets:
                    return
                sockets = list(self._sockets)
            payload = {"type": "stats", "data": _stats_snapshot()}
            stale = set()
            for ws in sockets:
                if ws.closed:
                    stale.add(ws)
                    continue
                try:
                    await ws.send_json(payload)
                except Exception:
                    stale.add(ws)
            if stale:
                async with self._lock:
                    for ws in stale:
                        self._sockets.discard(ws)


_stats_broker = _StatsBroker()


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
    """请求统计 + 系统资源 + 响应缓存命中率。"""
    return aiohttp.web.json_response(_stats_snapshot())


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


async def stats_ws(request: aiohttp.web.Request) -> aiohttp.web.WebSocketResponse:
    """WebSocket 端点：按固定间隔推送统计快照，替代客户端轮询。"""
    ws = aiohttp.web.WebSocketResponse(heartbeat=20.0)
    await ws.prepare(request)

    await _stats_broker.register(ws)
    try:
        try:
            if not ws.closed:
                await ws.send_json({"type": "hello"})
            if not ws.closed:
                await ws.send_json({"type": "stats", "data": _stats_snapshot()})
        except (ConnectionResetError, RuntimeError):
            return ws

        async for msg in ws:
            if msg.type == aiohttp.web.WSMsgType.TEXT:
                if msg.data == "ping":
                    await ws.send_json({"type": "pong"})
            elif msg.type in (aiohttp.web.WSMsgType.ERROR, aiohttp.web.WSMsgType.CLOSE):
                break
    finally:
        await _stats_broker.unregister(ws)

    return ws


async def requests_list(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """REST API：返回最近请求列表。"""
    limit = clamp_query_limit(request.query.get("limit", "50"))
    items = request_broker.get_recent(limit)
    return aiohttp.web.json_response({"requests": items})
