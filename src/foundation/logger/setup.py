from __future__ import annotations

"""集中日志配置模块。

提供 `get_logger` 以统一项目日志输出（控制台 + 文件）。
"""

import logging
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger as _loguru_logger

from .state import LOG_DIR, color_override, console_handler_id, initialized

_SENSITIVE_RE = re.compile(
    r"(?i)(api[_-]?key|token|password|authorization|secret|bearer)\s*[:=]\s*\S+",
)
_BEARER_RE = re.compile(r"(?i)(Bearer\s+)\S+")

# 日志等级映射（用于显示单字母）
LEVEL_ABBR = {
    "TRACE": "T",
    "DEBUG": "D",
    "INFO": "I",
    "SUCCESS": "S",
    "WARNING": "W",
    "ERROR": "E",
    "CRITICAL": "C",
}

_VALID_LOG_LEVELS = set(LEVEL_ABBR.keys())

_PARAMIKO_BENIGN_TOKENS = (
    "10054",
    "10053",
    "Socket exception",
    "EOF in transport",
)


def _suppress_paramiko_disconnect_noise() -> None:
    """抑制 paramiko 优雅断连时的噪音日志。"""
    logging.getLogger("paramiko").setLevel(logging.CRITICAL)


def _resolve_log_level() -> str:
    """解析日志级别，非法值回退 INFO。

    直接读取 config/main_config.toml 避免循环导入（src.foundation.config 导入 src.logger）。

    Returns:
        有效的日志级别字符串。
    """
    try:
        try:
            import tomllib
        except ModuleNotFoundError:
            import tomli as tomllib  # type: ignore[no-redef]

        root = Path(__file__).parent.parent.parent
        config_path = root / "config" / "main_config.toml"
        if config_path.exists():
            with open(config_path, "rb") as f:
                raw = tomllib.load(f)
            level = str(raw.get("debug", {}).get("level", "INFO")).upper()
            if level in _VALID_LOG_LEVELS:
                return level
    except Exception as exc:
        _loguru_logger.debug("读取 config/main_config.toml 日志级别失败: %s", exc)
    return "INFO"


def _resolve_log_name() -> str:
    """从 config/main_config.toml 读取日志名称，默认 provider-2。"""
    try:
        try:
            import tomllib
        except ModuleNotFoundError:
            import tomli as tomllib  # type: ignore[no-redef]

        root = Path(__file__).parent.parent.parent
        config_path = root / "config" / "main_config.toml"
        if config_path.exists():
            with open(config_path, "rb") as f:
                raw = tomllib.load(f)
            name = str(raw.get("debug", {}).get("log_name", "provider-2")).strip()
            if name:
                return name
    except Exception:
        pass
    return "provider-2"


def get_level_abbr(record: dict) -> str:
    """获取日志等级的单字母缩写。

    Args:
        record: loguru 日志记录字典。

    Returns:
        单字母缩写字符串。
    """
    level = record.get("level", "")
    if hasattr(level, "name"):
        level = level.name
    return LEVEL_ABBR.get(str(level).upper(), "?")


def set_color(enabled: bool | None) -> None:
    """动态设置日志颜色输出。

    Args:
        enabled: True 强制开启，False 强制关闭，None 恢复自动检测。
    """
    from .core import _setup_handlers

    state = __import__("src.foundation.logger.state", fromlist=["state"])
    state.color_override = enabled
    _setup_handlers()


def clean_old_logs(days: int = 30) -> None:
    """清理超过指定天数的旧日志文件。

    Args:
        days: 保留天数，默认 30 天。
    """
    if not LOG_DIR.exists():
        return
    cutoff = datetime.now() - timedelta(days=days)
    for log_file in LOG_DIR.glob("*.log"):
        try:
            if datetime.fromtimestamp(log_file.stat().st_mtime) < cutoff:
                log_file.unlink()
        except Exception:
            pass


def _redact_message(message: str) -> str:
    """遮蔽日志中的敏感凭据片段。"""
    if "WebUI Token:" in message:
        return message
    redacted = _BEARER_RE.sub(r"\1***", message)
    return _SENSITIVE_RE.sub(lambda m: m.group(0).split("=")[0] + "=***", redacted)


def _format_log(record: dict) -> bool:
    """格式化日志记录，确保 extra 字段存在。

    Args:
        record: loguru 日志记录字典。

    Returns:
        始终返回 True（用于 filter 回调）。
    """
    record["extra"]["level_abbr"] = get_level_abbr(record)
    if "module_name" not in record["extra"]:
        record["extra"]["module_name"] = "Adapter"
    try:
        record["message"] = _redact_message(str(record["message"]))
    except Exception:
        pass
    return True


class CompatLogger:
    """兼容标准 logging 调用风格的轻量包装器。

    支持 %-style 格式化参数，与现有代码中 logger.info("msg %s", arg)
    的调用方式完全兼容。
    """

    def __init__(self, module_logger: Any) -> None:
        """初始化兼容 logger。

        Args:
            module_logger: 底层 loguru bound logger 实例。
        """
        self._logger = module_logger

    @staticmethod
    def _render(message: str, args: tuple[Any, ...]) -> str:
        """渲染 %-style 格式化消息。

        Args:
            message: 格式字符串。
            args: 参数元组。

        Returns:
            渲染后的消息字符串。
        """
        if not args:
            return message
        try:
            return message % args
        except Exception:
            return "{} {}".format(message, " ".join(str(arg) for arg in args))

    def _log(self, level: str, message: str, *args: Any, **kwargs: Any) -> None:
        """内部日志记录方法。
        Args:
            level: 日志级别名称。
            message: 格式字符串。
            *args: 格式化参数。
            **kwargs: 额外关键字参数（如 exc_info）。
        """
        rendered = self._render(str(message), args)
        exc_info = kwargs.pop("exc_info", None)
        self._logger.opt(exception=exc_info if exc_info else None).log(level, rendered)

    def debug(self, message: str, *args: Any, **kwargs: Any) -> None:
        """记录 DEBUG 级别日志。"""
        self._log("DEBUG", message, *args, **kwargs)

    def info(self, message: str, *args: Any, **kwargs: Any) -> None:
        """记录 INFO 级别日志。"""
        self._log("INFO", message, *args, **kwargs)

    def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
        """记录 WARNING 级别日志。"""
        self._log("WARNING", message, *args, **kwargs)

    def error(self, message: str, *args: Any, **kwargs: Any) -> None:
        """记录 ERROR 级别日志。"""
        self._log("ERROR", message, *args, **kwargs)

    def exception(self, message: str, *args: Any, **kwargs: Any) -> None:
        """记录 EXCEPTION 级别日志（附带异常信息）。"""
        kwargs["exc_info"] = True
        self._log("ERROR", message, *args, **kwargs)

    def critical(self, message: str, *args: Any, **kwargs: Any) -> None:
        """记录 CRITICAL 级别日志。"""
        self._log("CRITICAL", message, *args, **kwargs)

    def success(self, message: str, *args: Any, **kwargs: Any) -> None:
        """记录 SUCCESS 级别日志（loguru 扩展）。"""
        self._log("SUCCESS", message, *args, **kwargs)

    def trace(self, message: str, *args: Any, **kwargs: Any) -> None:
        """记录 TRACE 级别日志（loguru 扩展）。"""
        self._log("TRACE", message, *args, **kwargs)

    def log(self, level: str, message: str, *args: Any, **kwargs: Any) -> None:
        """记录指定级别的日志。"""
        self._log(level, message, *args, **kwargs)
