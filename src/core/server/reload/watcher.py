from __future__ import annotations

"""向后兼容导出。"""

from src.core.server.infra.reload.service import HotReloadService

ReloadWatcher = HotReloadService
FileWatcher = HotReloadService

__all__ = ["FileWatcher", "HotReloadService", "ReloadWatcher"]
