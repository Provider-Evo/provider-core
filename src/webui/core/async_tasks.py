from __future__ import annotations

"""WebUI 异步任务管理器。"""

import asyncio
from abc import abstractmethod
from asyncio import Event, Lock, Task
from typing import Callable, Dict, Optional

from src.logger import get_logger

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
                    logger.error("等待任务 '%s' 完成时发生异常: %s", task.task_name, exc)
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
                        logger.error("任务 '%s' 执行异常: %s", task_name, exc, exc_info=True)
            self.tasks.clear()
            self.abort_flag.clear()
            logger.info("所有异步任务已停止")


async_task_manager = AsyncTaskManager()
