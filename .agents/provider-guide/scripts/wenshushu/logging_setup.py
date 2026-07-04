# -*- coding: utf-8 -*-
"""日志初始化模块。

提供 ``setup_logging`` 函数,统一配置日志格式与输出目标。
"""
from __future__ import annotations

import logging
import sys

# 日志格式（与 legacy 文件保持一致）
DEFAULT_LOG_FMT = "%(asctime)s|%(levelname)-8s|%(name)s:%(lineno)d| %(message)s"

_logger = logging.getLogger("use_wenshushu")


def setup_logging(
    level: int = logging.INFO,
    *,
    log_file: str | None = None,
    fmt: str = DEFAULT_LOG_FMT,
) -> None:
    """初始化日志系统。

    Args:
        level: 日志级别。
        log_file: 日志文件路径,为 None 时仅输出到控制台。
        fmt: 日志格式字符串。

    >>> setup_logging(logging.DEBUG)
    >>> _logger.level <= logging.DEBUG or _logger.parent.level <= logging.DEBUG
    True
    """
    root = logging.getLogger()
    root.setLevel(level)
    formatter = logging.Formatter(fmt)
    # 移除已有处理器避免重复
    for h in root.handlers[:]:
        root.removeHandler(h)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)
    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(formatter)
        root.addHandler(fh)
