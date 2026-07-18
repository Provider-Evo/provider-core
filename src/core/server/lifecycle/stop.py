"""shutdown 模块 — 项目标准模块。

职责：
    作为 Provider-Evo 项目标准模块，提供 shutdown 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""



from __future__ import annotations

from threading import Event

_shutdown_requested = Event()


def request_shutdown(reason: str = "") -> None:
    """标记当前进程正在关停。"""

    del reason
    _shutdown_requested.set()


def is_shutdown_requested() -> bool:
    """返回当前进程是否已经进入关停流程。"""

    return _shutdown_requested.is_set()
