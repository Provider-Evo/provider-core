"""plugin_progress 模块 — WebUI 层。

职责：
    作为 Provider-Evo 项目标准模块，提供 plugin_progress 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""


from __future__ import annotations

import time
from typing import Any, Dict, Optional

from src.foundation.logger import get_logger

__all__ = [
    "get_current_progress",
    "plugins_progress",
    "reset_progress",
    "update_progress",
]

logger = get_logger(__name__)

_current: Dict[str, Any] = {
    "operation": "idle",
    "stage": "idle",
    "progress": 0,
    "message": "",
    "error": None,
    "plugin_id": None,
}


def get_current_progress() -> Dict[str, Any]:
    return dict(_current)


def reset_progress() -> None:
    global _current
    _current = {
        "operation": "idle",
        "stage": "idle",
        "progress": 0,
        "message": "",
        "error": None,
        "plugin_id": None,
        "timestamp": time.time(),
    }


async def _broadcast(progress_data: Dict[str, Any]) -> None:
    try:
        from src.webui.internal.core.logs_ws import log_broker

        await log_broker.broadcast(
            {"type": "plugin_progress", "progress": progress_data},
        )
    except Exception as exc:
        logger.debug("插件进度广播失败: %s", exc)


async def _broadcast_summary_changed() -> None:
    try:
        from src.webui.internal.core.logs_ws import log_broker

        await log_broker.broadcast({"type": "summary_changed"})
    except Exception as exc:
        logger.debug("summary_changed 广播失败: %s", exc)


async def update_progress(
    stage: str,
    progress: int,
    message: str,
    *,
    operation: str = "install",
    error: Optional[str] = None,
    plugin_id: Optional[str] = None,
) -> None:
    global _current
    _current = {
        "operation": operation,
        "stage": stage,
        "progress": max(0, min(100, int(progress))),
        "message": message,
        "error": error,
        "plugin_id": plugin_id,
        "timestamp": time.time(),
    }
    await _broadcast(_current)
    if stage == "done":
        await _broadcast_summary_changed()
    logger.debug("插件进度 [%s] %s%% %s", stage, progress, message)


async def plugins_progress(_request: Any) -> Any:
    """GET /v1/admin/plugins/progress — 当前插件操作进度。"""
    import aiohttp.web

    return aiohttp.web.json_response(get_current_progress())
