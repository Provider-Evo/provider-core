"""logger 模块 - 由 logger.py 拆分而来。

原文件超过 800 行硬上限；按函数边界拆分为 2 个子模块。
本 __init__.py 重导出所有公共符号，保持外部 from .. import 路径稳定。
"""

from __future__ import annotations

from .core import (
    get_logger,
    shutdown_logging,
)
from .setup import (
    CompatLogger,
    clean_old_logs,
    get_level_abbr,
    set_color,
)

__all__ = [
    "CompatLogger",
    "clean_old_logs",
    "get_level_abbr",
    "get_logger",
    "set_color",
    "shutdown_logging",
]
