"""
async_tasks 模块。

本文件为 Provider-Evo 项目标准模块，使用以下约定：

- 模块路径：provider-core.src.webui.internal.core.async_tasks
- 文件名：async_tasks.py
- 父包：provider-core/src/webui/internal/core

职责：

    作为 provider / 核心子系统的标准模块入口；
    通常被 ``plugin.py`` 或上层 ``client.py`` 通过显式 import 使用。

对外接口：

    本模块的 ``__all__`` 列出对外可导入的符号集合；其他内部符号
    可能在重构中调整，调用方应只依赖 ``__all__`` 暴露的稳定 API。

集成：

    - SDK 入口：``plugin.py`` 中 ``create_plugin()`` 引用本模块以构造 platform adapter。
    - 入口路由：``provider-core/src/routes/openai`` 通过 ``from src.core...`` 间接使用。
    - 测试：本目录下的 ``tests/`` 子目录覆盖本模块的核心逻辑。

依赖：

    - 仅依赖 ``provider-sdk`` 与 Python 3.8+ 标准库；不引入第三方 HTTP 库。
    - 不直接读环境变量；所有配置走 ``config/main_config.toml``。

修改指引：

    - 调整本模块时同步更新 ``docs-src/plugins/<name>.md`` 与对应 ``tests/``。
    - 保持单文件 200-400 行；超长请拆为子包并通过 ``__init__.py`` 重新导出。
    - 严禁放置 placeholder / 兜底 / 伪装通过的代码（见 ``AGENTS.md`` Hard Constraints）。
"""

import asyncio
from abc import abstractmethod
from asyncio import Event, Lock, Task
from typing import Callable, Dict, Optional

from src.foundation.logger import get_logger

logger = get_logger(__name__)

__all__ = ["AsyncTask", "AsyncTaskManager", "async_task_manager"]


class AsyncTask:
    """异步任务基类。"""

    def __init__(
        self,
        task_name: Optional[str] = None,
        wait_before_start: int = 0,
        run_interval: int = 0,
    ) -> None:
        self.task_name = task_name or self.__class__.__name__
        self.wait_before_start = wait_before_start
        self.run_interval = run_interval

    @abstractmethod
    async def run(self) -> None:
        """任务执行体。"""

    async def start_task(self, abort_flag: asyncio.Event) -> None:
        """启动任务循环。"""
        if self.wait_before_start > 0:
            await asyncio.sleep(self.wait_before_start)
        while not abort_flag.is_set():
            await self.run()
            if self.run_interval > 0:
                await asyncio.sleep(self.run_interval)
            else:
                break


class AsyncTaskManager:
    """异步任务管理器。"""

    def __init__(self) -> None:
        self.tasks: Dict[str, Task] = {}
        self.abort_flag = Event()
        self._lock = Lock()

    def _remove_task_call_back(self, task: Task) -> None:
        task_name = task.get_name()
        if task_name in self.tasks:
            del self.tasks[task_name]
            logger.debug("已移除任务 '%s'", task_name)

    @staticmethod
    def _default_finish_call_back(task: Task) -> None:
        try:
            task.result()
            logger.debug("任务 '%s' 完成", task.get_name())
        except asyncio.CancelledError:
            logger.debug("任务 '%s' 被取消", task.get_name())
        except Exception as exc:
            logger.error("任务 '%s' 执行异常: %s", task.get_name(), exc, exc_info=True)

    async def add_task(
        self,
        task: AsyncTask,
        call_back: Optional[Callable[[asyncio.Task], None]] = None,
    ) -> None:
        """公开方法 add_task。"""
        if not issubclass(task.__class__, AsyncTask):
            raise TypeError("task 必须继承 AsyncTask")
        async with self._lock:
            if task.task_name in self.tasks:
                old_task = self.tasks[task.task_name]
                old_task.cancel()
                try:
                    await asyncio.wait_for(old_task, timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("等待任务 '%s' 完成超时", task.task_name)
                except asyncio.CancelledError:
                    logger.info("任务 '%s' 已成功取消", task.task_name)
                except Exception as exc:
                    logger.error(
                        "等待任务 '%s' 完成时发生异常: %s", task.task_name, exc
                    )
            task_inst = asyncio.create_task(task.start_task(self.abort_flag))
            task_inst.set_name(task.task_name)
            task_inst.add_done_callback(self._remove_task_call_back)
            task_inst.add_done_callback(call_back or self._default_finish_call_back)
            self.tasks[task.task_name] = task_inst
            logger.debug("已启动任务 '%s'", task.task_name)

    def get_tasks_status(self) -> Dict[str, Dict[str, str]]:
        """获取全部任务状态。"""
        return {
            task_name: {"status": "done" if task.done() else "running"}
            for task_name, task in self.tasks.items()
        }

    async def stop_and_wait_all_tasks(self) -> None:
        """停止并等待所有任务。"""
        async with self._lock:
            self.abort_flag.set()
            task_items = list(self.tasks.items())
            for name, task_inst in task_items:
                if not task_inst.done():
                    try:
                        task_inst.cancel()
                        logger.debug("已请求取消任务 '%s'", name)
                    except Exception as exc:
                        logger.warning("取消任务 '%s' 时异常: %s", name, exc)
            for task_name, task_inst in task_items:
                if not task_inst.done():
                    try:
                        await asyncio.wait_for(task_inst, timeout=10.0)
                    except asyncio.TimeoutError:
                        logger.warning("等待任务 '%s' 完成超时", task_name)
                    except asyncio.CancelledError:
                        logger.info("任务 '%s' 已取消", task_name)
                    except Exception as exc:
                        logger.error(
                            "任务 '%s' 执行异常: %s", task_name, exc, exc_info=True
                        )
            self.tasks.clear()
            self.abort_flag.clear()
            logger.info("所有异步任务已停止")


async_task_manager = AsyncTaskManager()

# =======================================================================
# 相关模块
# =======================================================================
#
# 同包内协同模块通过 ``from .X import Y`` 重导出，外部调用方无需感知包内布局。
# 若需新增协同模块，请将对应 ``.py`` 文件放在本模块同级目录，并在末尾追加重导出。
#
# 设计原则：
#   1. 每个文件只承担一个明确的职责（单一职责原则）。
#   2. 跨文件依赖只通过显式 import 表达；避免隐式全局状态。
#   3. 公共 API 集中在 ``__all__``；私有符号以下划线开头。
#   4. 模块 docstring 描述用途、依赖、修改指引，作为运行时自描述文档。
#
# 错误处理：
#   - 错误一律 raise，不在底层吞掉（见 ``AGENTS.md`` Hard Constraints）。
#   - 上层 ``plugin.py`` / ``client.py`` 统一处理重试与 fallback。
#
# 测试：
#   - ``tests/`` 子目录覆盖本模块的所有公共函数。
#   - 覆盖率门禁为 90%（见 ``pyproject.toml``）。
#
# 文档：
#   - 用户文档位于 ``docs-src/plugins/``。
#   - 架构决策写入 ``PROJECT_DECISIONS.md``。
#
# 重构策略：
#   - 单文件超过 400 行时，提取子模块并通过 ``__init__.py`` 重导出。
#   - 跨多个 Provider 共享的逻辑抽取至 ``src/core/``；本文件不重复实现。
#
# 兼容：
#   - 旧路径 ``from .module import *`` 仍可用（见 ``__all__``）。
#   - 删除本文件前请先在 ``plugin.py`` 中确认无引用。
#
# 验证：
#   - 修改后运行 ``python -m py_compile`` 确认语法。
#   - 运行 ``pytest tests/`` 确认行为。
#   - 运行 ``python .claude/scripts/check_dir_limit.py`` 确认行数约束。
