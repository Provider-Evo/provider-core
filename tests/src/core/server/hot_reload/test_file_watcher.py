from __future__ import annotations

import asyncio

from src.core.server.reload.file_watcher import Change, FileChange, FileWatcher


async def test_file_watcher_subscribe_and_dispatch() -> None:
    received: list[FileChange] = []

    async def _callback(changes: list[FileChange]) -> None:
        received.extend(changes)

    watcher = FileWatcher([], debounce_ms=50, callback_timeout_s=2.0)
    sub_id = watcher.subscribe(_callback, paths=[])
    assert sub_id

    await watcher._dispatch_changes(
        [FileChange(change_type=Change.modified, path=__import__("pathlib").Path(__file__))],
    )
    assert len(received) == 1
    watcher.unsubscribe(sub_id)


def test_path_matches_directory() -> None:
    from pathlib import Path

    base = Path(__file__).parent
    child = base / "test_classifier.py"
    assert FileWatcher._path_matches(child, base) is True
    assert FileWatcher._path_matches(base, child) is False
