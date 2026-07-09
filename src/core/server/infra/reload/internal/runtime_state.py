from __future__ import annotations

"""Worker 运行时状态 — 供 system/status 与重启 UX 使用。"""

import time
from typing import Optional

__all__ = ["get_worker_start_time", "set_worker_start_time"]

_worker_start_time: Optional[float] = None


def set_worker_start_time(start_time: Optional[float] = None) -> None:
    """记录 Worker 启动单调时钟（默认当前时间）。"""
    global _worker_start_time
    _worker_start_time = time.time() if start_time is None else start_time


def get_worker_start_time() -> float:
    """获取 Worker 启动时间戳。"""
    if _worker_start_time is None:
        return time.time()
    return _worker_start_time
