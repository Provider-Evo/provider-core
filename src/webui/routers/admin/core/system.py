
import time
from datetime import datetime

import aiohttp.web

from src.core.server.reload.internal.runtime_state import (
    get_hot_reload_service,
    get_worker_start_time,
)
from src.foundation.config import get_config, get_config_manager

__all__ = ["system_status"]


def _hot_reload_health() -> dict:
    """返回热重载文件监视器的健康状态（服务未启动时返回 unavailable）。"""
    service = get_hot_reload_service()
    if service is None:
        return {"status": "unavailable"}
    watcher = service.watcher
    if watcher is None:
        return {"status": "unavailable"}
    return watcher.get_health_status()


async def system_status(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/webui/system/status — 运行状态、uptime、版本、热重载健康状态。"""
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
            "hot_reload": _hot_reload_health(),
        },
    )
