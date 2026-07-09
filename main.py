#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

"""Provider-V2 主入口——Runner-Worker 双进程架构。

Runner 进程：
  - 守护 Worker 子进程
  - 监控退出码，处理自动重启（码 42）
  - 传递 Ctrl+C 给 Worker，Runner 本身不重启

Worker 进程：
  - asyncio 事件循环
  - 初始化全部子系统
  - 永久运行直到收到退出信号或触发重启

IDLE 环境：
  - 检测到 IDLE 时直接以单进程 Worker 模式运行
  - 文件监视器只提示，不触发重启
"""

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.resolve()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.paths import resolve_project_root as _resolve_project_root

_ROOT = _resolve_project_root()

import src.core.server  # noqa: F401 — 触发 proxy monkey-patch

from src.core.server.runner import run_runner
from src.core.server.worker import is_idle, run_worker


def main() -> None:
    """程序主入口——根据运行环境选择合适的启动模式。

    启动模式优先级：
    1. ``WORKER_PROCESS=1`` 环境变量：以 Worker 模式运行（由 Runner 启动）
    2. IDLE 环境：直接以 Worker 模式运行（单进程，禁用颜色）
    3. 其他：以 Runner 模式运行，由 Runner 守护 Worker 子进程
    """
    is_worker = os.environ.get("WORKER_PROCESS") == "1"

    if is_worker:
        run_worker()
    elif is_idle():
        print("IDLE 环境：直接以 Worker 模式运行（单进程）。", flush=True)
        os.environ["NO_COLOR"] = "1"
        os.environ.pop("CLICOLOR_FORCE", None)
        run_worker()
    else:
        run_runner()


if __name__ == "__main__":
    main()
