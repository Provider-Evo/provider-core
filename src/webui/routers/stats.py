from __future__ import annotations

"""WebUI 统计路由 — 请求统计 + 系统资源。"""

import os
import time

import aiohttp.web

from src.webui.services.stats import get_stats

__all__ = ["stats_api", "stats_reset"]


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
