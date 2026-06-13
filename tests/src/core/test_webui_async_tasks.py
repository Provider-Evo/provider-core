from __future__ import annotations

import asyncio

from src.webui.core.async_tasks import AsyncTask, AsyncTaskManager


class _DemoTask(AsyncTask):
    def __init__(self) -> None:
        super().__init__(task_name='demo-task')
        self.ran = False

    async def run(self) -> None:
        self.ran = True


def test_async_task_manager_lifecycle() -> None:
    async def runner() -> None:
        manager = AsyncTaskManager()
        task = _DemoTask()
        await manager.add_task(task)
        await asyncio.sleep(0)
        status = manager.get_tasks_status()
        assert 'demo-task' in status
        await manager.stop_and_wait_all_tasks()
        assert manager.tasks == {}
        assert task.ran is True

    asyncio.run(runner())
