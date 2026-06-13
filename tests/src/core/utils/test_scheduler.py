"""Tests for src/core/utils/scheduler.py."""
import asyncio

import pytest

from src.core.utils.scheduler import TaskScheduler


class TestTaskScheduler:
    @pytest.mark.asyncio
    async def test_submit_single_task(self):
        scheduler = TaskScheduler(max_concurrent=3)

        async def my_task():
            return "done"

        result = await scheduler.submit("task1", my_task())
        assert result == "done"

    @pytest.mark.asyncio
    async def test_cancel_all(self):
        scheduler = TaskScheduler(max_concurrent=3)

        async def long_task():
            await asyncio.sleep(100)

        # Submit task but cancel before it completes
        task = asyncio.create_task(scheduler.submit("task1", long_task()))
        await asyncio.sleep(0.01)  # Let task start
        await scheduler.cancel_all()

        with pytest.raises(asyncio.CancelledError):
            await task

    @pytest.mark.asyncio
    async def test_cancel_all_clears_active_tasks(self):
        scheduler = TaskScheduler(max_concurrent=3)

        async def long_task():
            await asyncio.sleep(100)

        asyncio.create_task(scheduler.submit("task1", long_task()))
        await asyncio.sleep(0.01)

        status = scheduler.get_status()
        assert status["active_count"] == 1

        await scheduler.cancel_all()
        status = scheduler.get_status()
        assert status["active_count"] == 0

    @pytest.mark.asyncio
    async def test_get_status(self):
        scheduler = TaskScheduler(max_concurrent=5)

        status = scheduler.get_status()
        assert status["max_concurrent"] == 5
        assert status["active_count"] == 0
        assert status["active_tasks"] == []

    @pytest.mark.asyncio
    async def test_get_status_with_active_tasks(self):
        scheduler = TaskScheduler(max_concurrent=3)

        async def long_task():
            await asyncio.sleep(100)

        # Start a task but don't await it
        future = asyncio.create_task(scheduler.submit("task1", long_task()))
        await asyncio.sleep(0.01)  # Let it start

        status = scheduler.get_status()
        assert status["active_count"] >= 1
        assert "task1" in status["active_tasks"]

        # Clean up
        await scheduler.cancel_all()
        future.cancel()
        try:
            await future
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_max_concurrent_limit(self):
        scheduler = TaskScheduler(max_concurrent=2)

        started = []
        completed = []

        async def task(name):
            started.append(name)
            await asyncio.sleep(0.05)
            completed.append(name)
            return name

        # Submit 3 tasks, only 2 should run concurrently
        results = await asyncio.gather(
            scheduler.submit("t1", task("t1")),
            scheduler.submit("t2", task("t2")),
            scheduler.submit("t3", task("t3")),
        )

        assert sorted(results) == ["t1", "t2", "t3"]
        # First two should start before third
        assert started.index("t3") > started.index("t1") or started.index("t3") > started.index("t2")

    @pytest.mark.asyncio
    async def test_task_failure_removes_from_active(self):
        scheduler = TaskScheduler(max_concurrent=3)

        async def failing_task():
            raise RuntimeError("task failed")

        with pytest.raises(RuntimeError):
            await scheduler.submit("fail1", failing_task())

        status = scheduler.get_status()
        assert status["active_count"] == 0
        assert "fail1" not in status["active_tasks"]

    @pytest.mark.asyncio
    async def test_concurrent_submissions(self):
        scheduler = TaskScheduler(max_concurrent=10)

        async def simple_task(n):
            await asyncio.sleep(0.01)
            return n * 2

        tasks = [scheduler.submit(f"task{i}", simple_task(i)) for i in range(10)]
        results = await asyncio.gather(*tasks)
        assert sorted(results) == [i * 2 for i in range(10)]
