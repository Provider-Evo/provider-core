from __future__ import annotations

"""通用异步文件监视器。"""

import asyncio
import time
import uuid
from pathlib import Path
from typing import Iterable, Optional

from src.core.server.reload.file_watcher.backend import FileWatcherBackendMixin
from src.core.server.reload.file_watcher.disp import FileWatcherDispatchMixin
from src.core.server.reload.file_watcher.health import FileWatcherHealthMixin
from src.core.server.reload.file_watcher.types import (
    Change,
    ChangeCallback,
    FileChange,
    FileWatcherStats,
    FileWatchSubscription,
    _SubscriptionState,
)
from src.foundation.logger import get_logger

__all__ = [
    "Change",
    "FileChange",
    "FileWatcher",
    "FileWatcherStats",
]

logger = get_logger(__name__)


class FileWatcher(
    FileWatcherHealthMixin, FileWatcherDispatchMixin, FileWatcherBackendMixin
):
    """订阅式文件监视器：debounce、回调超时与失败冷却。

    增强点：
    1. 健康检查机制：定期检查内存使用、回调成功率等指标
    2. 性能监控：记录内存使用和 CPU 使用率
    3. 健康状态 API：提供健康状态查询接口
    """

    def __init__(
        self,
        paths: Iterable[Path],
        *,
        debounce_ms: int = 600,
        callback_timeout_s: float = 15.0,
        callback_failure_threshold: int = 3,
        callback_cooldown_s: float = 30.0,
        force_polling: bool = False,
    ) -> None:
        self._paths = [path.resolve() for path in paths]
        self._debounce_ms = debounce_ms
        self._force_polling = force_polling
        self._callback_timeout_s = callback_timeout_s
        self._callback_failure_threshold = callback_failure_threshold
        self._callback_cooldown_s = callback_cooldown_s
        self._running = False
        self._task: Optional[asyncio.Task[None]] = None
        self._ready_event = asyncio.Event()
        self._subscriptions: dict[str, FileWatchSubscription] = {}
        self._subscription_states: dict[str, _SubscriptionState] = {}
        self._stats = FileWatcherStats()
        # 启动冷却期：避免重启后立即检测到旧文件变更导致循环重启
        self._startup_grace_s: float = 10.0
        self._started_at: float = 0.0
        # 健康检查相关
        self._health_check_interval = 30.0  # 30秒检查一次
        self._last_health_check = 0.0
        self._health_status = "healthy"
        self._memory_usage: list[float] = []  # MB
        self._cpu_usage: list[float] = []  # 百分比

    @property
    def running(self) -> bool:
        return self._running

    @property
    def stats(self) -> FileWatcherStats:
        return FileWatcherStats(
            batches_seen=self._stats.batches_seen,
            changes_seen=self._stats.changes_seen,
            callbacks_succeeded=self._stats.callbacks_succeeded,
            callbacks_failed=self._stats.callbacks_failed,
            callbacks_timed_out=self._stats.callbacks_timed_out,
            callbacks_skipped_cooldown=self._stats.callbacks_skipped_cooldown,
            restart_count=self._stats.restart_count,
        )

    def subscribe(
        self,
        callback: ChangeCallback,
        *,
        paths: Iterable[Path] | None = None,
        change_types: Iterable[Change] | None = None,
    ) -> str:
        """注册文件变更回调。"""
        if not callable(callback):
            raise TypeError("callback 必须是可调用对象")
        normalized_paths = (
            tuple(path.resolve() for path in paths) if paths is not None else ()
        )
        normalized_change_types = (
            frozenset(change_types) if change_types is not None else None
        )
        subscription_id = str(uuid.uuid4())
        self._subscriptions[subscription_id] = FileWatchSubscription(
            subscription_id=subscription_id,
            callback=callback,
            paths=normalized_paths,
            change_types=normalized_change_types,
        )
        self._subscription_states[subscription_id] = _SubscriptionState()
        return subscription_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """注销订阅。"""
        removed = self._subscriptions.pop(subscription_id, None) is not None
        self._subscription_states.pop(subscription_id, None)
        return removed

    async def start(self) -> None:
        """启动后台监视任务。"""
        if self._running:
            return
        if not self._subscriptions:
            raise RuntimeError("启动文件监视器前必须至少注册一个订阅")
        self._running = True
        self._started_at = time.monotonic()
        self._ready_event = asyncio.Event()
        self._task = asyncio.create_task(self._run())
        await self._ready_event.wait()

    async def stop(self) -> None:
        """停止监视任务。"""
        if not self._running:
            return
        self._running = False
        if self._task is None:
            return
        self._task.cancel()
        # watchfiles 后台任务须 await 清理，否则 stop 后仍占用 inotify/句柄
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None
        stats = self.stats
        logger.info(
            "文件监视器已停止: batches=%d changes=%d ok=%d failed=%d timeout=%d cooldown_skip=%d restart=%d",
            stats.batches_seen,
            stats.changes_seen,
            stats.callbacks_succeeded,
            stats.callbacks_failed,
            stats.callbacks_timed_out,
            stats.callbacks_skipped_cooldown,
            stats.restart_count,
        )
