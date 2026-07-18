"""文件监视器 — watchfiles / watchdog 后端运行循环混入。"""

from __future__ import annotations

import asyncio
from pathlib import Path

from src.foundation.logger import get_logger
from src.core.server.reload.file_watcher.types import Change, FileChange, _map_watchfiles_change

__all__ = ["FileWatcherBackendMixin"]

logger = get_logger(__name__)

try:
    from watchfiles import awatch

    _USE_WATCHFILES = True
except ImportError:
    awatch = None  # type: ignore[misc, assignment]
    _USE_WATCHFILES = False


class FileWatcherBackendMixin:
    """watchfiles/watchdog 运行循环能力混入。

    依赖宿主类提供: _running, _ready_event, _paths, _debounce_ms,
    _force_polling, _stats, _dispatch_changes()。
    """

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

    def _build_watchdog_handler(self, loop, queue):
        from watchdog.events import FileSystemEventHandler

        class _Handler(FileSystemEventHandler):
            """watchdog 事件转发到 asyncio 队列。"""

            def _emit(self, path: str, change_type: Change) -> None:
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    [FileChange(change_type=change_type, path=Path(path).resolve())],
                )

            def on_modified(self, event: object) -> None:
                if event.is_directory if hasattr(event, "is_directory") else False:
                    return
                self._emit(event.src_path, Change.modified)

            def on_created(self, event: object) -> None:
                if event.is_directory if hasattr(event, "is_directory") else False:
                    return
                self._emit(event.src_path, Change.added)

            def on_deleted(self, event: object) -> None:
                if event.is_directory if hasattr(event, "is_directory") else False:
                    return
                self._emit(event.src_path, Change.deleted)

            def on_moved(self, event: object) -> None:
                dest = event.dest_path if hasattr(event, "dest_path") else None
                is_dir = event.is_directory if hasattr(event, "is_directory") else False
                if dest and not is_dir:
                    self._emit(dest, Change.modified)

        return _Handler()

    def _start_watchdog_observer(self, handler):
        from watchdog.observers import Observer

        observer = Observer()
        for base in self._paths:
            if base.is_dir():
                observer.schedule(handler, str(base), recursive=True)
            elif base.is_file():
                observer.schedule(handler, str(base.parent), recursive=False)
        observer.start()
        return observer

    async def _drain_watchdog_queue(self, queue: "asyncio.Queue") -> None:
        debounce_s = self._debounce_ms / 1000.0
        pending: list = []
        while self._running:
            try:
                batch = await asyncio.wait_for(queue.get(), timeout=debounce_s)
                pending.extend(batch)
            except asyncio.TimeoutError:
                if pending:
                    await self._dispatch_changes(pending)
                    pending = []

    async def _run_watchdog(self) -> None:
        loop = asyncio.get_running_loop()
        queue: "asyncio.Queue" = asyncio.Queue()
        handler = self._build_watchdog_handler(loop, queue)
        observer = self._start_watchdog_observer(handler)
        if not self._ready_event.is_set():
            self._ready_event.set()
        try:
            await self._drain_watchdog_queue(queue)
        finally:
            observer.stop()
            observer.join(timeout=5.0)

    def _normalize_watchfiles_changes(self, changes: set) -> list:
        normalized: list = []
        for change, path in changes:
            normalized.append(
                FileChange(
                    change_type=_map_watchfiles_change(change),
                    path=Path(path).resolve(),
                ),
            )
        return normalized
