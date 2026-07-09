from __future__ import annotations

"""热重载服务 — 统一 FileWatcher（单监视器多订阅）。"""

from pathlib import Path
from typing import Any, Optional, Sequence

from src.logger import get_logger

from src.core.server.infra.reload.coordinator import ReloadCoordinator
from src.core.server.infra.reload.file_watcher import FileChange, FileWatcher

__all__ = ["HotReloadService"]

logger = get_logger(__name__)

_SOURCE_EXTENSIONS = {".py", ".js", ".css", ".html", ".toml"}


class HotReloadService:
    """持有单个 ``FileWatcher``，订阅源码、主配置与 WebUI 配置。"""

    def __init__(
        self,
        root: Path,
        registry: Any,
        session: Any,
        app_host: Any,
        config_manager: Any,
        *,
        dry_run: bool = False,
    ) -> None:
        self._root = root.resolve()
        self._config_manager = config_manager
        self._coordinator = ReloadCoordinator(
            registry,
            session,
            app_host,
            dry_run=dry_run,
        )
        self._watcher: Optional[FileWatcher] = None
        self._source_sub_id: Optional[str] = None
        self._main_config_sub_id: Optional[str] = None
        self._webui_config_sub_id: Optional[str] = None

    @property
    def coordinator(self) -> ReloadCoordinator:
        """公开方法 coordinator。"""
        return self._coordinator

    async def start(self) -> None:
        """启动统一文件监视器。"""
        watch_paths: list[Path] = []
        src = self._root / "src"
        if src.is_dir():
            watch_paths.append(src)
        main_py = self._root / "main.py"
        if main_py.is_file():
            watch_paths.append(main_py)

        main_config_path = self._config_manager._config_path
        if main_config_path is not None:
            watch_paths.append(Path(main_config_path))

        from src.paths import config_dir

        webui_config_path = config_dir() / "webui_config.toml"
        if webui_config_path.is_file():
            watch_paths.append(webui_config_path)

        self._watcher = FileWatcher(
            watch_paths,
            debounce_ms=600,
            callback_timeout_s=15.0,
            callback_failure_threshold=3,
            callback_cooldown_s=30.0,
        )

        source_paths = [p for p in watch_paths if p.name not in {"main_config.toml", "webui_config.toml"}]
        self._source_sub_id = self._watcher.subscribe(
            self._on_source_changes,
            paths=source_paths,
        )

        if main_config_path is not None:
            self._main_config_sub_id = self._config_manager.attach_file_watcher(
                self._watcher,
                Path(main_config_path),
            )

        if webui_config_path.is_file():
            self._webui_config_sub_id = self._watcher.subscribe(
                self._on_webui_config_changes,
                paths=[webui_config_path.resolve()],
            )

        await self._watcher.start()
        logger.info("热重载服务已启动: %s", self._root)

    async def stop(self) -> None:
        """停止监视器并输出统计。"""
        if self._watcher is None:
            return
        stats = self._watcher.stats
        for sub_id in (self._source_sub_id, self._main_config_sub_id, self._webui_config_sub_id):
            if sub_id is not None:
                self._watcher.unsubscribe(sub_id)
        self._source_sub_id = None
        self._main_config_sub_id = None
        self._webui_config_sub_id = None
        await self._watcher.stop()
        self._watcher = None
        logger.info(
            "热重载服务已停止: batches=%d changes=%d ok=%d failed=%d timeout=%d cooldown_skip=%d restart=%d",
            stats.batches_seen,
            stats.changes_seen,
            stats.callbacks_succeeded,
            stats.callbacks_failed,
            stats.callbacks_timed_out,
            stats.callbacks_skipped_cooldown,
            stats.restart_count,
        )

    async def _on_source_changes(self, changes: Sequence[FileChange]) -> None:
        paths = {
            str(change.path)
            for change in changes
            if self._accept_source_change(change)
        }
        if paths:
            await self._coordinator.handle_changes(paths)

    async def _on_webui_config_changes(self, changes: Sequence[FileChange]) -> None:
        names = sorted({change.path.name for change in changes})
        if names:
            logger.debug("WebUI 配置已变更（跳过热重载，API 按需读取）: %s", names)

    @staticmethod
    def _accept_source_change(change: FileChange) -> bool:
        path = change.path
        if path.name in {"main_config.toml", "webui_config.toml"}:
            return False
        if path.suffix and path.suffix not in _SOURCE_EXTENSIONS:
            return False
        return True
