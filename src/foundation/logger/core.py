from __future__ import annotations

"""logger 核心模块 - handler 初始化与 logger 工厂。"""

import sys
from typing import Any, Optional

from loguru import logger as _loguru_logger

from .state import LOG_DIR, color_override, console_handler_id, initialized
from .setup import (
    _resolve_log_level,
    _resolve_log_name,
    _format_log,
    _suppress_paramiko_disconnect_noise,
    CompatLogger,
)


def _supports_color() -> bool:
    """检测终端是否支持 ANSI 颜色输出。"""
    import os

    if color_override is not None:
        return color_override

    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR") or os.environ.get("CLICOLOR_FORCE"):
        return True

    term = os.environ.get("TERM", "")
    if term and term != "dumb":
        return True

    if sys.platform == "win32":
        if "WT_SESSION" in os.environ:
            return True
        if os.environ.get("ANSICON"):
            return True

    return sys.stderr.isatty()


def _get_windows_color_sink() -> Any:
    """在 Windows 上返回经过 colorama 包装的 stderr sink。"""
    if sys.platform != "win32":
        return sys.stderr
    try:
        from colorama import AnsiToWin32
        return AnsiToWin32(sys.stderr, convert=None, strip=False, autoreset=False).stream
    except ImportError:
        return sys.stderr


def _load_early_color_override() -> Optional[bool]:
    """在 loguru handler 初始化前，尝试直接读取配置文件中的 debug.color 设置。"""
    try:
        try:
            import tomllib
        except ModuleNotFoundError:
            import tomli as tomllib  # type: ignore[no-redef]
        _cfg = LOG_DIR.parent / "config" / "main_config.toml"
        if _cfg.exists():
            with open(_cfg, "rb") as _f:
                _raw = tomllib.load(_f)
            return _raw.get("debug", {}).get("color", True)
    except Exception:
        pass
    return None


def _build_console_format(use_color: bool) -> str:
    """构造控制台日志格式字符串，按是否支持颜色决定是否加 loguru 标签。"""
    if not use_color:
        return (
            "{time:MM-DD HH:mm:ss} | "
            "[ {extra[level_abbr]} ] | "
            "{extra[module_name]} | "
            "{message}"
        )
    return (
        "<blue>{time:MM-DD HH:mm:ss}</blue> | "
        "<level>[ {extra[level_abbr]} ]</level> | "
        "<cyan>{extra[module_name]}</cyan> | "
        "<level>{message}</level>"
    )


def _add_console_handler(log_level: str) -> None:
    """添加控制台 handler，并记录 handler id 供后续调整颜色时移除重建。"""
    import src.foundation.logger.state as state

    use_color = _supports_color()
    console_format = _build_console_format(use_color)

    state.console_handler_id = _loguru_logger.add(
        _get_windows_color_sink() if use_color else sys.stderr,
        level=log_level,
        colorize=use_color,
        format=console_format,
        filter=_format_log,
        enqueue=False,
    )


def _add_file_handler() -> None:
    """添加文件 handler，按天滚动写入 LOG_DIR。"""
    log_name = _resolve_log_name()
    _loguru_logger.add(
        str(LOG_DIR / "{}-{{time:YYYYMMDD-HHmmss}}.log".format(log_name)),
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
        # 不用 enqueue=True：Runner/Worker 是各自独立进程（subprocess.Popen），
        # 不存在跨进程共享写入需求；enqueue=True 依赖 multiprocessing.SimpleQueue，
        # 其内部具名信号量在 finalize_exit() 的 os._exit() 硬退出下无法被
        # resource_tracker 正常 unlink，导致 Linux/macOS 上出现信号量泄漏警告。
        enqueue=False,
        filter=_format_log,
    )


def _setup_handlers() -> None:
    """移除 loguru 默认 handler，添加控制台与文件 handler（仅执行一次）。"""
    import src.foundation.logger.state as state

    if state.initialized:
        return

    from .setup import clean_old_logs

    clean_old_logs(30)

    _loguru_logger.remove()
    log_level = _resolve_log_level()

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    _early_color = _load_early_color_override()
    if _early_color is not None:
        state.color_override = _early_color

    _add_console_handler(log_level)
    _add_file_handler()

    state.initialized = True
    _suppress_paramiko_disconnect_noise()


_setup_handlers()


def _cleanup_loguru() -> None:
    """在进程退出前移除所有 loguru handler，避免 atexit 回调中 join 线程阻塞。"""
    try:
        _loguru_logger.remove()
    except Exception:
        pass


def shutdown_logging() -> None:
    """优雅关闭日志系统，释放文件句柄与后台线程。"""
    _cleanup_loguru()


import atexit as _atexit
_atexit.register(_cleanup_loguru)


def get_logger(module_name: str) -> CompatLogger:
    """返回绑定了模块名的 logger。

    Args:
        module_name: 通常传入 ``__name__``。

    Returns:
        CompatLogger 实例。
    """
    return CompatLogger(_loguru_logger.bind(module_name=module_name))


# 默认 logger 实例（向后兼容）
logger = _loguru_logger.bind(module_name=_resolve_log_name())
