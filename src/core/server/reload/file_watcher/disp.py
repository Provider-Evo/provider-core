"""文件监视器 — 变更分发、回调重试与冷却混入。"""

from __future__ import annotations

import asyncio
from typing import Sequence

from src.core.server.reload.file_watcher.types import (
    Change,
    ChangeCallback,
    FileChange,
    FileWatchSubscription,
)
from src.foundation.logger import get_logger

__all__ = ["FileWatcherDispatchMixin"]

logger = get_logger(__name__)


class FileWatcherDispatchMixin:
    """变更事件分发能力混入。

    依赖宿主类提供: _started_at, _startup_grace_s, _stats, _subscriptions,
    _subscription_states, _callback_timeout_s, _callback_failure_threshold,
    _callback_cooldown_s。
    """

    def _within_startup_grace(self) -> bool:
        if self._started_at <= 0:
            return False
        elapsed = asyncio.get_event_loop().time() - self._started_at
        return elapsed < self._startup_grace_s

    async def _dispatch_changes(self, changes: Sequence[FileChange]) -> None:
        """分发文件变更事件到订阅者。"""
        if self._within_startup_grace():
            logger.debug("启动冷却期内忽略变更")
            return

        self._stats.batches_seen += 1
        self._stats.changes_seen += len(changes)
        for subscription in list(self._subscriptions.values()):
            await self._dispatch_to_subscription(subscription, changes)

    async def _dispatch_to_subscription(
        self, subscription: FileWatchSubscription, changes: Sequence[FileChange]
    ) -> None:
        matched = self._match_changes(changes, subscription)
        if not matched:
            return
        state = self._subscription_states.get(subscription.subscription_id)
        if state is None:
            return
        now_monotonic = asyncio.get_running_loop().time()
        if state.cooldown_until_monotonic > now_monotonic:
            self._stats.callbacks_skipped_cooldown += 1
            return
        await self._invoke_with_retry(subscription, matched, state)

    async def _invoke_with_retry(self, subscription, matched, state) -> None:
        max_retries = 2
        for attempt in range(max_retries):
            try:
                await asyncio.wait_for(
                    self._invoke_callback(subscription.callback, matched),
                    timeout=self._callback_timeout_s,
                )
                state.consecutive_failures = 0
                self._stats.callbacks_succeeded += 1
                return
            except asyncio.TimeoutError:
                if attempt < max_retries - 1:
                    logger.warning(
                        "文件变更回调超时，重试 %d/%d (subscription_id=%s)",
                        attempt + 1,
                        max_retries,
                        subscription.subscription_id,
                    )
                    continue
                self._stats.callbacks_timed_out += 1
                self._stats.callbacks_failed += 1
                self._mark_callback_failure(subscription.subscription_id)
                logger.warning(
                    "文件变更回调超时 (subscription_id=%s, timeout=%ss)",
                    subscription.subscription_id,
                    self._callback_timeout_s,
                )
                return
            except Exception as exc:
                self._stats.callbacks_failed += 1
                self._mark_callback_failure(subscription.subscription_id)
                logger.warning(
                    "文件变更回调失败 (subscription_id=%s): %s",
                    subscription.subscription_id,
                    exc,
                )
                return

    async def _invoke_callback(
        self, callback: ChangeCallback, changes: Sequence[FileChange]
    ) -> None:
        if asyncio.iscoroutinefunction(callback):
            await callback(changes)
            return
        await asyncio.get_running_loop().run_in_executor(None, callback, changes)

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
        self, changes: Sequence[FileChange], subscription: FileWatchSubscription
    ) -> list:
        matched: list = []
        for change in changes:
            if (
                subscription.change_types is not None
                and change.change_type not in subscription.change_types
            ):
                continue
            if subscription.paths and not any(
                self._path_matches(change.path, path) for path in subscription.paths
            ):
                continue
            matched.append(change)
        return matched

    @staticmethod
    def _path_matches(changed_path, subscribed_path) -> bool:
        if subscribed_path.is_dir():
            if changed_path == subscribed_path:
                return True
            try:
                changed_path.relative_to(subscribed_path)
                return True
            except ValueError:
                return False
        return changed_path == subscribed_path
