"""runtime_state 模块 — 项目标准模块。

职责：
    作为 Provider-Evo 项目标准模块，提供 runtime_state 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""

import time
from typing import Any, Optional

__all__ = [
    "get_worker_start_time",
    "set_worker_start_time",
    "get_hot_reload_service",
    "set_hot_reload_service",
]

_worker_start_time: Optional[float] = None
_hot_reload_service: Optional[Any] = None


def set_worker_start_time(start_time: Optional[float] = None) -> None:
    """记录 Worker 启动单调时钟（默认当前时间）。"""
    global _worker_start_time
    _worker_start_time = time.time() if start_time is None else start_time


def get_worker_start_time() -> float:
    """获取 Worker 启动时间戳。"""
    if _worker_start_time is None:
        return time.time()
    return _worker_start_time


def set_hot_reload_service(service: Optional[Any]) -> None:
    """记录当前 Worker 的 HotReloadService 实例，供状态查询接口读取。"""
    global _hot_reload_service
    _hot_reload_service = service


def get_hot_reload_service() -> Optional[Any]:
    """获取当前 Worker 的 HotReloadService 实例（可能为 None）。"""
    return _hot_reload_service
