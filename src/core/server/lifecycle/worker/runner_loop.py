"""Runner Worker 守护主循环。"""

from __future__ import annotations

import subprocess
import threading
import time
from typing import Optional

from src.foundation.logger import get_logger

logger = get_logger(__name__)


def _worker_loop_iteration(
    args: list,
    worker_env: dict,
    max_error_restarts: int,
    error_restart_count: int,
    spawn_worker,
    wait_worker,
    handle_worker_exit,
) -> tuple:
    proc, reader_thread = spawn_worker(args, worker_env)
    if proc is None:
        return None, None, error_restart_count, True, False

    worker_started_at = time.time()
    exit_code = wait_worker(proc, reader_thread)
    if exit_code is None:
        return proc, reader_thread, error_restart_count, False, True

    if reader_thread is not None:
        reader_thread.join(timeout=2.0)

    worker_runtime = time.time() - worker_started_at
    if exit_code == 0 and worker_runtime < 3.0:
        logger.warning(
            "Worker 在 %.1f 秒内正常退出；若服务未启动，请检查 1337 端口是否已被占用"
            "（netstat -ano | findstr 1337）或查看上方 Worker 日志",
            worker_runtime,
        )

    error_restart_count, give_up = handle_worker_exit(
        exit_code, error_restart_count, max_error_restarts
    )
    return proc, reader_thread, error_restart_count, give_up, False


def run_worker_loop(
    args: list,
    worker_env: dict,
    max_error_restarts: int,
    *,
    spawn_worker,
    wait_worker,
    check_rapid_restart,
    handle_worker_exit,
) -> tuple:
    """执行 Worker 守护主循环，返回最终的进程与读取线程句柄。"""
    rapid_restart_count = 0
    error_restart_count = 0
    last_start_time: float = 0.0
    proc: Optional[subprocess.Popen] = None
    reader_thread: Optional[threading.Thread] = None

    while True:
        elapsed = time.time() - last_start_time
        rapid_restart_count, give_up = check_rapid_restart(
            rapid_restart_count, elapsed
        )
        if give_up:
            break
        last_start_time = time.time()

        proc, reader_thread, error_restart_count, give_up, early = (
            _worker_loop_iteration(
                args,
                worker_env,
                max_error_restarts,
                error_restart_count,
                spawn_worker,
                wait_worker,
                handle_worker_exit,
            )
        )
        if early:
            return proc, reader_thread, True
        if give_up:
            break

    return proc, reader_thread, False
