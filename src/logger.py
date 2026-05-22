"""Loguru 日志模块——替代标准 logging。"""

from __future__ import annotations

import sys
from typing import Any, Optional

try:
    from loguru import logger as _loguru_logger
except ImportError:
    _loguru_logger = None

__all__ = ["get_logger", "CompatLogger"]


class CompatLogger:
    """兼容标准 logging.Logger 接口的 Loguru 包装器。"""

    def __init__(self, name: str = "") -> None:
        self._name = name

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log("DEBUG", msg, args)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log("INFO", msg, args)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log("WARNING", msg, args)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log("ERROR", msg, args)

    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log("CRITICAL", msg, args)

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log("ERROR", msg, args)

    def _log(self, level: str, msg: str, args: Any) -> None:
        if args:
            msg = msg % args
        if _loguru_logger is not None:
            _loguru_logger.log(level, msg)
        else:
            import logging
            logging.getLogger(self._name).log(
                getattr(logging, level, logging.INFO), msg
            )


def get_logger(name: str = "") -> CompatLogger:
    """获取日志记录器。"""
    return CompatLogger(name)


def setup_logging(level: str = "INFO") -> None:
    """配置 Loguru 日志。"""
    if _loguru_logger is not None:
        from loguru import logger
        logger.remove()
        logger.add(
            sys.stderr,
            level=level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        )
