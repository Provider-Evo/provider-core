from __future__ import annotations

"""集中日志配置模块。

提供 `get_logger` 以统一项目日志输出（控制台 + 文件）。
日志格式严格遵循 task.txt 第 11 节规范。
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger as _loguru_logger

# 当 CLICOLOR_FORCE=1 时，loguru 的 colorize=True 在管道下仍然会输出 ANSI 代码
# 通过自定义 sink 强制 loguru 始终渲染颜色标记

# 标记是否已完成基础 handler 初始化，避免重复添加
_initialized: bool = False

_LOG_DIR = Path(__file__).parent.parent / "logs"

# 全局颜色覆盖：None 表示自动检测，True/False 强制开启/关闭
_color_override: bool | None = None

# 控制台 handler ID（用于 set_color 时移除并重建）
_console_handler_id: int | None = None

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


def _resolve_log_level() -> str:
    """解析日志级别，非法值回退 INFO。

    直接读取 config.toml 避免循环导入（src.core.config 导入 src.logger）。

    Returns:
        有效的日志级别字符串。
    """
    try:
        import tomllib
        from pathlib import Path

        # 查找 config.toml
        root = Path(__file__).parent.parent
        config_path = root / "config.toml"
        if config_path.exists():
            with open(config_path, "rb") as f:
                raw = tomllib.load(f)
            level = str(raw.get("debug", {}).get("level", "INFO")).upper()
            if level in _VALID_LOG_LEVELS:
                return level
    except Exception as exc:
        _loguru_logger.debug("读取 config.toml 日志级别失败: %s", exc)
    return "INFO"


def get_level_abbr(record: dict) -> str:
    """获取日志等级的单字母缩写。

    Args:
        record: loguru 日志记录字典。

    Returns:
        单字母缩写字符串。
    """
    return LEVEL_ABBR.get(record["level"].name, record["level"].name[0])


def set_color(enabled: bool | None) -> None:
    """设置日志颜色开关。

    初始化后调用会重建控制台 handler 以立即生效。

    Args:
        enabled: True 强制开启颜色，False 强制关闭，None 恢复自动检测。
    """
    global _color_override, _console_handler_id
    _color_override = enabled

    # 初始化完成后重建 console handler，使颜色变更立即生效
    if _initialized and _console_handler_id is not None:
        _loguru_logger.remove(_console_handler_id)
        use_color = _supports_color()
        log_level = _resolve_log_level()

        console_format = (
            "{time:MM-DD HH:mm:ss} | "
            "[ {extra[level_abbr]} ] | "
            "{extra[module_name]} | "
            "{message}"
        )
        if use_color:
            console_format = (
                "<blue>{time:MM-DD HH:mm:ss}</blue> | "
                "<level>[ {extra[level_abbr]} ]</level> | "
                "<cyan>{extra[module_name]}</cyan> | "
                "<level>{message}</level>"
            )

        _console_handler_id = _loguru_logger.add(
            sys.stderr,
            level=log_level,
            colorize=use_color,
            format=console_format,
            filter=_format_log,
            enqueue=False,
        )


def clean_old_logs(days: int = 30) -> None:
    """清理超过指定天数的日志文件。

    Args:
        days: 保留天数，默认 30 天。
    """
    try:
        cutoff_date = datetime.now() - timedelta(days=days)
        for log_file in _LOG_DIR.glob("*.log"):
            try:
                file_time = datetime.fromtimestamp(log_file.stat().st_mtime)
                if file_time < cutoff_date:
                    log_file.unlink()
            except OSError as exc:
                _loguru_logger.debug("清理过期日志文件 %s 失败: %s", log_file, exc)
    except Exception as exc:
        _loguru_logger.debug("清理过期日志失败: %s", exc)


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
        """记录 DEBUG 级别日志。

        Args:
            message: 格式字符串。
            *args: 格式化参数。
            **kwargs: 额外关键字参数。
        """
        self._log("DEBUG", message, *args, **kwargs)

    def info(self, message: str, *args: Any, **kwargs: Any) -> None:
        """记录 INFO 级别日志。

        Args:
            message: 格式字符串。
            *args: 格式化参数。
            **kwargs: 额外关键字参数。
        """
        self._log("INFO", message, *args, **kwargs)

    def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
        """记录 WARNING 级别日志。

        Args:
            message: 格式字符串。
            *args: 格式化参数。
            **kwargs: 额外关键字参数。
        """
        self._log("WARNING", message, *args, **kwargs)

    def error(self, message: str, *args: Any, **kwargs: Any) -> None:
        """记录 ERROR 级别日志。

        Args:
            message: 格式字符串。
            *args: 格式化参数。
            **kwargs: 额外关键字参数。
        """
        self._log("ERROR", message, *args, **kwargs)

    def exception(self, message: str, *args: Any, **kwargs: Any) -> None:
        """记录 ERROR 级别日志并附带异常堆栈。

        Args:
            message: 格式字符串。
            *args: 格式化参数。
            **kwargs: 额外关键字参数。
        """
        kwargs["exc_info"] = True
        self._log("ERROR", message, *args, **kwargs)


def _supports_color() -> bool:
    """检测终端是否支持 ANSI 颜色输出。

    检测顺序：
    1. 全局覆盖（set_color）→ 直接返回
    2. NO_COLOR → 禁用
    3. FORCE_COLOR / CLICOLOR_FORCE → 启用
    4. TERM 环境变量（xterm, msys, cygwin 等）→ 启用
    5. Windows Terminal (WT_SESSION) / ANSICON → 启用
    6. sys.stdout.isatty() → 启用
    """
    import os

    # 全局覆盖优先
    if _color_override is not None:
        return _color_override

    # 用户显式禁用
    if os.environ.get("NO_COLOR"):
        return False
    # 用户显式强制（Worker 进程通过管道输出时依赖此变量）
    if os.environ.get("FORCE_COLOR") or os.environ.get("CLICOLOR_FORCE"):
        return True

    # TERM 变量：Git Bash (msys/cygwin)、大多数现代终端
    term = os.environ.get("TERM", "")
    if term and term != "dumb":
        return True

    # Windows 特定检测
    if sys.platform == "win32":
        if "WT_SESSION" in os.environ:  # Windows Terminal
            return True
        if os.environ.get("ANSICON"):
            return True

    # 回退：tty 检测
    return sys.stdout.isatty()


def _setup_handlers() -> None:
    """移除 loguru 默认 handler，添加控制台与文件 handler（仅执行一次）。

    控制台处理器：简洁格式 MM-DD HH:mm:ss | [I] | ModuleName | message
    文件处理器：详细格式 YYYY-MM-DD HH:mm:ss.SSS | [LEVEL] | ModuleName | name:function:line - message
    """
    global _initialized, _console_handler_id, _color_override
    if _initialized:
        return

    # 清理过期日志
    clean_old_logs(30)

    # 移除 loguru 内置的 stderr handler
    _loguru_logger.remove()
    log_level = _resolve_log_level()

    # 确保日志目录存在
    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    # 尽早读取 config 中的颜色设置（在 ConfigManager 初始化之前）
    _early_color = None
    try:
        import tomllib
        _cfg = Path(__file__).parent.parent / "config.toml"
        if _cfg.exists():
            with open(_cfg, "rb") as _f:
                _raw = tomllib.load(_f)
            _early_color = _raw.get("debug", {}).get("color", True)
    except Exception:
        pass
    if _early_color is not None:
        _color_override = _early_color

    # 检测颜色支持
    use_color = _supports_color()

    console_format = (
        "{time:MM-DD HH:mm:ss} | "
        "[ {extra[level_abbr]} ] | "
        "{extra[module_name]} | "
        "{message}"
    )
    if use_color:
        console_format = (
            "<blue>{time:MM-DD HH:mm:ss}</blue> | "
            "<level>[ {extra[level_abbr]} ]</level> | "
            "<cyan>{extra[module_name]}</cyan> | "
            "<level>{message}</level>"
        )

    _console_handler_id = _loguru_logger.add(
        sys.stderr,
        level=log_level,
        colorize=use_color,
        format=console_format,
        filter=_format_log,
        enqueue=False,
    )

    # 文件输出处理器 - 详细格式，记录所有 TRACE 级别
    _loguru_logger.add(
        str(_LOG_DIR / "provider-v2_{time:YYYYMMDD_HHmmss}.log"),
        level="TRACE",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
            "[{level}] | "
            "{extra[module_name]} | "
            "{name}:{function}:{line} - "
            "{message}"
        ),
        rotation="100 MB",
        retention="30 days",
        encoding="utf-8",
        enqueue=True,
        filter=_format_log,
    )

    _initialized = True


_setup_handlers()


def get_logger(module_name: str) -> CompatLogger:
    """返回绑定了模块名的 logger。

    Args:
        module_name: 通常传入 ``__name__``。

    Returns:
        CompatLogger 实例。

    Example:
        >>> from src.logger import get_logger
        >>> logger = get_logger("MyModule")
        >>> logger.info("这是一条日志")
        MM-DD HH:mm:ss | [I] | MyModule | 这是一条日志
    """
    return CompatLogger(_loguru_logger.bind(module_name=module_name))


# 默认 logger 实例（向后兼容）
logger = _loguru_logger.bind(module_name="Adapter")
