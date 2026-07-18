"""main 模块 — 项目标准模块。

职责：
    作为 Provider-Evo 项目标准模块，提供 main 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""



import os
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.resolve()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.foundation.paths import resolve_project_root as _resolve_project_root

_ROOT = _resolve_project_root()

import src.core.server  # noqa: F401 — 触发 proxy monkey-patch

from src.core.server.lifecycle.runner import run_runner
from src.core.server.lifecycle.worker.worker import is_idle, run_worker
from src.foundation.logger import get_logger

logger = get_logger(__name__)


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
        logger.info("IDLE 环境：直接以 Worker 模式运行（单进程）")
        os.environ["NO_COLOR"] = "1"
        os.environ.pop("CLICOLOR_FORCE", None)
        run_worker()
    else:
        run_runner()


if __name__ == "__main__":
    main()
