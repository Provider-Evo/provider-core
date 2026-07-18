"""文件监视器 — 变更事件类型与订阅状态数据结构。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Awaitable, Callable, Sequence, Union

__all__ = [
    "Change",
    "FileChange",
    "ChangeCallback",
    "FileWatchSubscription",
    "_SubscriptionState",
    "FileWatcherStats",
    "_map_watchfiles_change",
]


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


ChangeCallback = Callable[[Sequence[FileChange]], Union[Awaitable[None], None]]


@dataclass(frozen=True)
class FileWatchSubscription:
    """订阅条目。"""

    subscription_id: str
    callback: ChangeCallback
    paths: tuple[Path, ...]
    change_types: frozenset[Change] | None


@dataclass
class _SubscriptionState:
    """单个订阅的失败计数与冷却状态。"""

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
    name = change.name.lower() if hasattr(change, "name") else str(change).lower()
    if name in {"added", "1"}:
        return Change.added
    if name in {"deleted", "3"}:
        return Change.deleted
    return Change.modified
