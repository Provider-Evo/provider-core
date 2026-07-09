from __future__ import annotations

"""通用异步文件监视器。"""

import asyncio
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Awaitable, Callable, Iterable, Optional, Sequence

from src.logger import get_logger

__all__ = [
    "Change",
    "FileChange",
    "FileWatcher",
    "FileWatcherStats",
]

logger = get_logger(__name__)

try:
    from watchfiles import Change as _WatchfilesChange
    from watchfiles import awatch

    _USE_WATCHFILES = True
except ImportError:
    _WatchfilesChange = None  # type: ignore[misc, assignment]
    awatch = None  # type: ignore[misc, assignment]
    _USE_WATCHFILES = False


class Change(str, Enum):
    """文件变更类型（与 watchfiles.Change 对齐）。"""

    added = "added"
    modified = "modified"
    deleted = "deleted"


@dataclass(frozen=True)
class FileChange:
    """单次文件变更事件。"""

    change_type: Change
    path: Path


ChangeCallback = Callable[[Sequence[FileChange]], Awaitable[None] | None]


@dataclass(frozen=True)
class FileWatchSubscription:
    """订阅条目。"""

    subscription_id: str
    callback: ChangeCallback
    paths: tuple[Path, ...]
    change_types: frozenset[Change] | None


@dataclass
class _SubscriptionState:
    """公开类 _SubscriptionState。"""
    consecutive_failures: int = 0
    cooldown_until_monotonic: float = 0.0


@dataclass
class FileWatcherStats:
    """监视器运行统计。"""

    batches_seen: int = 0
    changes_seen: int = 0
    callbacks_succeeded: int = 0
    callbacks_failed: int = 0
    callbacks_timed_out: int = 0
    callbacks_skipped_cooldown: int = 0
    restart_count: int = 0


def _map_watchfiles_change(change: object) -> Change:
    name = getattr(change, "name", str(change)).lower()
    if name in {"added", "1"}:
        return Change.added
    if name in {"deleted", "3"}:
        return Change.deleted
    return Change.modified


class FileWatcher:
    """订阅式文件监视器：debounce、回调超时与失败冷却。"""

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

    @property
    def running(self) -> bool:
        """公开方法 running。"""
        return self._running

    @property
    def stats(self) -> FileWatcherStats:
        """公开方法 stats。"""
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
        normalized_paths = tuple(path.resolve() for path in paths) if paths is not None else ()
        normalized_change_types = frozenset(change_types) if change_types is not None else None
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

    async def _run(self) -> None:
        while self._running:
            try:
                if not self._ready_event.is_set():
                    self._ready_event.set()
                if _USE_WATCHFILES and awatch is not None:
                    await self._run_watchfiles()
                else:
                    await self._run_watchdog()
            except asyncio.CancelledError:
                return
            except Exception as exc:
                self._stats.restart_count += 1
                logger.error("文件监视器运行异常，将在 1 秒后重试: %s", exc)
                if self._running:
                    await asyncio.sleep(1.0)

    async def _run_watchfiles(self) -> None:
        assert awatch is not None
        async for changes in awatch(
            *self._paths,
            debounce=self._debounce_ms,
            force_polling=self._force_polling,
            yield_on_timeout=True,
        ):
            if not self._running:
                break
            if not changes:
                continue
            normalized = self._normalize_watchfiles_changes(changes)
            if normalized:
                await self._dispatch_changes(normalized)

    async def _run_watchdog(self) -> None:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[list[FileChange]] = asyncio.Queue()
        watcher = self

        class _Handler(FileSystemEventHandler):
            """公开类 _Handler。"""
            def _emit(self, path: str, change_type: Change) -> None:
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    [FileChange(change_type=change_type, path=Path(path).resolve())],
                )

            def on_modified(self, event: object) -> None:
                """公开方法 on_modified。"""
                if getattr(event, "is_directory", False):
                    return
                self._emit(event.src_path, Change.modified)

            def on_created(self, event: object) -> None:
                """公开方法 on_created。"""
                if getattr(event, "is_directory", False):
                    return
                self._emit(event.src_path, Change.added)

            def on_deleted(self, event: object) -> None:
                """公开方法 on_deleted。"""
                if getattr(event, "is_directory", False):
                    return
                self._emit(event.src_path, Change.deleted)

            def on_moved(self, event: object) -> None:
                """公开方法 on_moved。"""
                dest = getattr(event, "dest_path", None)
                if dest and not getattr(event, "is_directory", False):
                    self._emit(dest, Change.modified)

        observer = Observer()
        handler = _Handler()
        for base in self._paths:
            if base.is_dir():
                observer.schedule(handler, str(base), recursive=True)
            elif base.is_file():
                observer.schedule(handler, str(base.parent), recursive=False)
        observer.start()
        if not self._ready_event.is_set():
            self._ready_event.set()
        debounce_s = self._debounce_ms / 1000.0
        pending: list[FileChange] = []
        try:
            while self._running:
                try:
                    batch = await asyncio.wait_for(queue.get(), timeout=debounce_s)
                    pending.extend(batch)
                except asyncio.TimeoutError:
                    if pending:
                        await self._dispatch_changes(pending)
                        pending = []
        finally:
            observer.stop()
            observer.join(timeout=5.0)

    async def _dispatch_changes(self, changes: Sequence[FileChange]) -> None:
        self._stats.batches_seen += 1
        self._stats.changes_seen += len(changes)
        for subscription in list(self._subscriptions.values()):
            matched = self._match_changes(changes, subscription)
            if not matched:
                continue
            state = self._subscription_states.get(subscription.subscription_id)
            if state is None:
                continue
            now_monotonic = asyncio.get_running_loop().time()
            if state.cooldown_until_monotonic > now_monotonic:
                self._stats.callbacks_skipped_cooldown += 1
                continue
            try:
                await asyncio.wait_for(
                    self._invoke_callback(subscription.callback, matched),
                    timeout=self._callback_timeout_s,
                )
                state.consecutive_failures = 0
                self._stats.callbacks_succeeded += 1
            except asyncio.TimeoutError:
                self._stats.callbacks_timed_out += 1
                self._stats.callbacks_failed += 1
                self._mark_callback_failure(subscription.subscription_id)
                logger.warning(
                    "文件变更回调超时 (subscription_id=%s, timeout=%ss)",
                    subscription.subscription_id,
                    self._callback_timeout_s,
                )
            except Exception as exc:
                self._stats.callbacks_failed += 1
                self._mark_callback_failure(subscription.subscription_id)
                logger.warning(
                    "文件变更回调失败 (subscription_id=%s): %s",
                    subscription.subscription_id,
                    exc,
                )

    async def _invoke_callback(
        self,
        callback: ChangeCallback,
        changes: Sequence[FileChange],
    ) -> None:
        if asyncio.iscoroutinefunction(callback):
            await callback(changes)
            return
        await asyncio.to_thread(callback, changes)

    def _mark_callback_failure(self, subscription_id: str) -> None:
        state = self._subscription_states.get(subscription_id)
        if state is None:
            return
        state.consecutive_failures += 1
        if state.consecutive_failures >= self._callback_failure_threshold:
            now_monotonic = asyncio.get_running_loop().time()
            state.cooldown_until_monotonic = now_monotonic + self._callback_cooldown_s
            state.consecutive_failures = 0
            logger.warning(
                "文件变更回调进入冷却 (subscription_id=%s, cooldown=%ss)",
                subscription_id,
                self._callback_cooldown_s,
            )

    def _match_changes(
        self,
        changes: Sequence[FileChange],
        subscription: FileWatchSubscription,
    ) -> list[FileChange]:
        matched: list[FileChange] = []
        for change in changes:
            if subscription.change_types is not None and change.change_type not in subscription.change_types:
                continue
            if subscription.paths and not any(
                self._path_matches(change.path, path) for path in subscription.paths
            ):
                continue
            matched.append(change)
        return matched

    @staticmethod
    def _path_matches(changed_path: Path, subscribed_path: Path) -> bool:
        if subscribed_path.is_dir():
            if changed_path == subscribed_path:
                return True
            try:
                changed_path.relative_to(subscribed_path)
                return True
            except ValueError:
                return False
        return changed_path == subscribed_path

    def _normalize_watchfiles_changes(
        self,
        changes: set[tuple[object, str]],
    ) -> list[FileChange]:
        normalized: list[FileChange] = []
        for change, path in changes:
            normalized.append(
                FileChange(
                    change_type=_map_watchfiles_change(change),
                    path=Path(path).resolve(),
                ),
            )
        return normalized
