from __future__ import annotations

"""热重载协调器 — 分类并调度 L0–L4（debounce 由 FileWatcher 负责）。

增强点：
1. 添加请求排队机制，热重载期间将请求加入队列
2. 实现请求等待和通知机制
3. 支持热重载状态跟踪
"""

import asyncio
from pathlib import Path
from typing import Any, List, Optional, Set

from src.foundation.logger import get_logger

from src.core.server.reload.clsfy import ClassifyResult, classify_paths
from src.core.server.reload.restart import request_process_restart

__all__ = ["ReloadCoordinator"]

logger = get_logger(__name__)

_EXECUTE_TIMEOUT_S = 30.0
_QUEUE_MAX_SIZE = 100  # 队列最大长度
_QUEUE_WAIT_TIMEOUT_S = 30.0  # 队列等待超时


class ReloadCoordinator:
    """接收文件变更路径，分类并调度 L0–L4 热重载动作。

    增强点：
    1. 请求排队机制：热重载期间将请求加入队列
    2. 请求等待和通知机制：热重载完成后通知等待的请求
    3. 热重载状态跟踪：跟踪当前热重载状态
    """

    def __init__(
        self,
        registry: Any,
        session: Any,
        app_host: Any,
        *,
        dry_run: bool = False,
    ) -> None:
        self._registry = registry
        self._session = session
        self._app_host = app_host
        self._dry_run = dry_run
        self._execute_lock = asyncio.Lock()
        # 请求排队机制
        self._request_queue: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_MAX_SIZE)
        self._is_reloading = False
        self._pending_requests: List[asyncio.Future] = []
        self._reload_count = 0

    @property
    def is_reloading(self) -> bool:
        """返回当前是否正在热重载。"""
        return self._is_reloading

    @property
    def reload_count(self) -> int:
        """返回热重载次数。"""
        return self._reload_count

    async def _enqueue_while_reloading(self, paths: Set[str]) -> None:
        """热重载进行中时，把变更加入队列并等待本轮重载完成。"""
        try:
            future = asyncio.get_running_loop().create_future()
            self._pending_requests.append(future)
            await asyncio.wait_for(
                self._request_queue.put(paths),
                timeout=5.0,
            )
            logger.debug("热重载进行中，请求已加入队列")
            try:
                await asyncio.wait_for(future, timeout=_QUEUE_WAIT_TIMEOUT_S)
            except asyncio.TimeoutError:
                logger.warning("热重载队列等待超时 (%ss)", _QUEUE_WAIT_TIMEOUT_S)
        except asyncio.TimeoutError:
            logger.warning("热重载队列已满，丢弃请求")

    def _notify_pending_requests(self) -> None:
        """通知所有等待中的请求本轮重载已完成。"""
        for future in self._pending_requests:
            if not future.done():
                future.set_result(True)
        self._pending_requests.clear()

    async def _drain_queued_changes(self) -> None:
        """依次处理队列中排队的变更集合。"""
        while not self._request_queue.empty():
            try:
                queued_paths = await asyncio.wait_for(
                    self._request_queue.get(),
                    timeout=1.0,
                )
                await asyncio.wait_for(
                    self._execute(queued_paths),
                    timeout=_EXECUTE_TIMEOUT_S,
                )
            except asyncio.TimeoutError:
                logger.warning("队列处理超时")
                break
            except asyncio.QueueEmpty:
                break

    async def _run_reload_cycle(self, paths: Set[str]) -> None:
        """在持锁状态下执行一轮热重载：等待旧请求、执行、通知、清空队列。"""
        try:
            # 等待现有请求完成
            await self._drain_pending_requests()

            await asyncio.wait_for(
                self._execute(paths),
                timeout=_EXECUTE_TIMEOUT_S,
            )
            self._reload_count += 1

            self._notify_pending_requests()
            await self._drain_queued_changes()

        except asyncio.TimeoutError:
            logger.error("热重载执行超时 (%ss)", _EXECUTE_TIMEOUT_S)
        finally:
            self._is_reloading = False

    async def handle_changes(self, paths: Set[str]) -> None:
        """接收一批文件变更并执行热重载。

        增强点：
        1. 热重载期间将请求加入队列
        2. 等待现有请求完成
        3. 处理队列中的变更
        """
        if not paths:
            return

        if self._is_reloading:
            await self._enqueue_while_reloading(paths)
            return

        async with self._execute_lock:
            self._is_reloading = True
            await self._run_reload_cycle(paths)

    async def _drain_pending_requests(self) -> None:
        """等待现有请求完成。"""
        if not self._pending_requests:
            return

        logger.debug("等待 %d 个现有请求完成", len(self._pending_requests))
        for future in self._pending_requests:
            if not future.done():
                try:
                    await asyncio.wait_for(future, timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("等待请求完成超时")

    async def _execute(self, paths: Set[str]) -> None:
        names = [Path(p).name for p in paths]
        result = classify_paths(paths)
        logger.debug("热重载分类 %s -> %s", names, result)

        if self._dry_run:
            self._log_idle_hint(names, result)
            return

        if result.process:
            await request_process_restart(
                registry=self._registry,
                session=self._session,
                reason="core 或启动文件变更: {}".format(", ".join(names)),
            )
            return

        if result.platforms:
            await self._reload_platforms(result.platforms)

        if result.plugin_manifest_sync:
            await self._sync_plugin_manifests(result.plugin_manifest_sync)

        if result.plugins:
            plugin_ids = frozenset(
                pid for pid in result.plugins if pid not in result.plugin_manifest_sync
            )
            if plugin_ids:
                await self._reload_plugins(
                    plugin_ids,
                    reload_app=result.plugin_app_reload,
                )

        if result.application:
            await self._reload_application(names)

        if result.static:
            await self._notify_static_changed(names)

    async def _reload_platforms(self, platforms: frozenset[str]) -> None:
        await self._registry.reload_platforms(sorted(platforms), self._session)

    async def _reload_plugins(
        self, plugin_ids: frozenset[str], *, reload_app: bool = True
    ) -> None:
        await self._registry.reload_plugins_by_ids(
            sorted(plugin_ids),
            self._session,
            reload_app=reload_app,
        )

    async def _sync_plugin_manifests(self, plugin_ids: frozenset[str]) -> None:
        for plugin_id in sorted(plugin_ids):
            await self._registry.sync_plugin_manifest(
                plugin_id,
                self._session,
                reload_app=True,
            )

    async def _reload_application(self, names: list[str]) -> None:
        if self._app_host is None:
            await request_process_restart(
                registry=self._registry,
                session=self._session,
                reason="应用路由变更但 AppHost 不可用: {}".format(", ".join(names)),
            )
            return
        try:
            await self._app_host.reload_app()
        except Exception as exc:
            logger.error("应用热重载失败，回退进程重启: %s", exc, exc_info=True)
            await request_process_restart(
                registry=self._registry,
                session=self._session,
                reason="应用热重载失败",
            )

    async def _notify_static_changed(self, names: list[str]) -> None:
        logger.info("前端静态资源变更: %s", names)
        try:
            from src.core.utils.compat.observability import get_observability_services

            await get_observability_services().broadcast_log(
                {
                    "type": "static_changed",
                    "files": names,
                    "message": "前端静态资源已更新，请手动刷新页面",
                },
            )
        except Exception as exc:
            logger.debug("静态资源变更通知失败: %s", exc)

    @staticmethod
    def _log_idle_hint(names: list[str], result: ClassifyResult) -> None:
        logger.info("IDLE 检测到文件变更: %s -> %s", names, result)
        logger.warning("IDLE 文件变更 {}，请手动重启 (python main.py)".format(names))
