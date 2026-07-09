from __future__ import annotations

"""Runner 进程：守护 Worker 子进程并处理自动重启。"""

import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import IO, Optional

from src.core.server.lifecycle.worker import RESTART_EXIT_CODE, finalize_exit
from src.foundation.logger import get_logger
from src.foundation.paths import resolve_project_root

__all__ = [
    "run_runner",
]

_MAX_RAPID_RESTARTS = 10
_RAPID_RESTART_THRESHOLD = 5.0
_RESTART_COOLDOWN = 1.0
_ERROR_RESTART_DELAY = 10.0
_DEFAULT_MAX_ERROR_RESTARTS = 3

_ROOT = resolve_project_root()

logger = get_logger(__name__)


def _read_color_config() -> bool:
    """从 config/main_config.toml 读取 debug.color 配置项。

    在 Python 3.11+ 使用标准库 tomllib；低版本尝试第三方 tomli；
    均不可用或文件不存在时默认返回 True（启用颜色）。

    Returns:
        color 配置值，默认 True。
    """
    cfg_path = _ROOT / "config" / "main_config.toml"
    if not cfg_path.exists():
        return True

    if sys.version_info >= (3, 11):
        import tomllib

        try:
            with open(cfg_path, "rb") as fh:
                raw = tomllib.load(fh)
            return bool(raw.get("debug", {}).get("color", True))
        except (tomllib.TOMLDecodeError, OSError):
            return True

    try:
        import tomli  # type: ignore[import]

        with open(cfg_path, "rb") as fh:
            raw = tomli.load(fh)
        return bool(raw.get("debug", {}).get("color", True))
    except ImportError:
        logger.debug("tomli 未安装，跳过 color 配置读取，默认启用颜色")
        return True
    except Exception:
        return True


def _build_worker_env(color_enabled: bool) -> dict:
    """构建 Worker 子进程的环境变量字典。

    Args:
        color_enabled: 是否启用 ANSI 颜色输出。

    Returns:
        环境变量字典（基于当前进程环境的副本）。
    """
    env = os.environ.copy()
    env["WORKER_PROCESS"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    if color_enabled:
        env["CLICOLOR_FORCE"] = "1"
        env.pop("NO_COLOR", None)
    else:
        env.pop("CLICOLOR_FORCE", None)
        env["NO_COLOR"] = "1"

    return env


def _describe_exit_code(exit_code: int) -> str:
    """将子进程退出码转为可读说明。"""
    if exit_code == RESTART_EXIT_CODE:
        return f"退出码 {exit_code}（请求重启）"
    if exit_code < 0:
        signal_num = -exit_code
        known = {
            6: "SIGABRT",
            9: "SIGKILL",
            11: "SIGSEGV 段错误",
            15: "SIGTERM",
        }
        label = known.get(signal_num, f"信号 {signal_num}")
        return f"退出码 {exit_code}（{label}）"
    return f"退出码 {exit_code}"


def _pipe_reader(stream: IO[bytes]) -> None:
    """在后台线程中持续读取子进程输出并写入当前进程的 stdout。

    以二进制模式读取，decode 时使用 errors="replace" 容错，
    避免子进程输出非 UTF-8 字节时崩溃。

    Args:
        stream: 子进程的 stdout 字节流（``subprocess.PIPE``）。
    """
    while True:
        line = stream.readline()
        if not line:
            break
        try:
            sys.stdout.write(line.decode("utf-8", errors="replace"))
            sys.stdout.flush()
        except (OSError, ValueError):
            pass


def run_runner() -> None:
    """Runner 进程入口——守护 Worker 子进程，处理自动重启。

    重启策略：
    - Worker 以退出码 42 退出时触发重启，冷却 1 秒后再启动新 Worker。
    - 若在 ``_RAPID_RESTART_THRESHOLD`` 秒内连续快速重启超过
      ``_MAX_RAPID_RESTARTS`` 次，Runner 放弃重启并退出。
    - Worker 以其他退出码退出时（错误退出），等待 10 秒后重启，
      但最多重启 ``max_restarts`` 次（默认 3 次）。
    - Runner 收到 Ctrl+C 时，立即终止 Worker 并退出。
    """
    color_enabled = _read_color_config()
    worker_env = _build_worker_env(color_enabled)

    python = sys.executable
    args = [python, "-u", str(_ROOT / "main.py")]

    max_error_restarts = _DEFAULT_MAX_ERROR_RESTARTS
    try:
        from src.core.config import get_config

        cfg = get_config()
        max_error_restarts = getattr(cfg.server, "max_restarts", _DEFAULT_MAX_ERROR_RESTARTS)
    except Exception:
        pass

    rapid_restart_count = 0
    error_restart_count = 0
    last_start_time: float = 0.0

    proc: Optional[subprocess.Popen] = None
    reader_thread: Optional[threading.Thread] = None

    while True:
        now = time.time()
        elapsed = now - last_start_time

        if elapsed < _RAPID_RESTART_THRESHOLD:
            rapid_restart_count += 1
            if rapid_restart_count > _MAX_RAPID_RESTARTS:
                logger.error(
                    "Worker 在 %.1f 秒内连续快速重启 %d 次，Runner 放弃重启并退出",
                    _RAPID_RESTART_THRESHOLD,
                    rapid_restart_count,
                )
                break
            logger.warning(
                "快速重启检测：第 %d 次（上限 %d 次）",
                rapid_restart_count,
                _MAX_RAPID_RESTARTS,
            )
        else:
            rapid_restart_count = 0

        last_start_time = time.time()

        logger.debug("启动 Worker 子进程...")
        worker_started_at = time.time()

        try:
            proc = subprocess.Popen(
                args,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=worker_env,
            )
        except OSError as exc:
            logger.error("无法启动 Worker 进程: %s", exc)
            break

        assert proc.stdout is not None, "proc.stdout 不应为 None（已指定 PIPE）"

        reader_thread = threading.Thread(
            target=_pipe_reader,
            args=(proc.stdout,),
            daemon=True,
            name=f"pipe-reader-{proc.pid}",
        )
        reader_thread.start()

        exit_code: int
        try:
            exit_code = proc.wait()
        except KeyboardInterrupt:
            logger.info("Runner 收到 Ctrl+C，正在终止 Worker (PID=%d)...", proc.pid)
            proc.terminate()
            try:
                proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            if reader_thread is not None:
                reader_thread.join(timeout=2.0)
            logger.info("Worker 已终止，Runner 退出")
            finalize_exit(0)

        if reader_thread is not None:
            reader_thread.join(timeout=2.0)

        worker_runtime = time.time() - worker_started_at
        if exit_code == 0 and worker_runtime < 3.0:
            logger.warning(
                "Worker 在 %.1f 秒内正常退出；若服务未启动，请检查 1337 端口是否已被占用"
                "（netstat -ano | findstr 1337）或查看上方 Worker 日志",
                worker_runtime,
            )

        if exit_code == RESTART_EXIT_CODE:
            logger.info(
                "触发自动重启（退出码 %d），冷却 %.1f 秒后重启...",
                exit_code,
                _RESTART_COOLDOWN,
            )
            time.sleep(_RESTART_COOLDOWN)
        elif exit_code != 0:
            error_restart_count += 1
            if error_restart_count > max_error_restarts:
                logger.error(
                    "Worker 因错误退出 %d 次（最大 %d 次），Runner 放弃重启并退出",
                    error_restart_count - 1,
                    max_error_restarts,
                )
                break
            logger.warning(
                "Worker 因错误退出（%s），等待 %.1f 秒后重启（第 %d/%d 次）...",
                _describe_exit_code(exit_code),
                _ERROR_RESTART_DELAY,
                error_restart_count,
                max_error_restarts,
            )
            time.sleep(_ERROR_RESTART_DELAY)
        else:
            logger.info("Worker 正常退出（退出码 %d），Runner 退出", exit_code)
            break

    if proc is not None and proc.poll() is None:
        proc.kill()
        proc.wait()
    if reader_thread is not None:
        reader_thread.join(timeout=2.0)
    finalize_exit(0)
