from __future__ import annotations

"""系统状态与重启 API。"""

import time
from datetime import datetime

import aiohttp.web

from src.core.config import get_config, get_config_manager
from src.core.server.reload.internal.runtime_state import get_worker_start_time

__all__ = ["system_status"]


async def system_status(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/webui/system/status — 运行状态、uptime、版本。"""
    cfg = get_config()
    start_time = get_worker_start_time()
    uptime = time.time() - start_time
    mgr = get_config_manager()
    return aiohttp.web.json_response(
        {
            "running": True,
            "uptime": uptime,
            "version": cfg.server.version,
            "start_time": datetime.fromtimestamp(start_time).isoformat(),
            "reload_revision": mgr.reload_revision,
        },
    )
