from __future__ import annotations

"""File watcher — hot-reload platforms, detect core changes for restart."""

import asyncio
import importlib
import os
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple

from echotools.logger.manager import get_logger
from echotools.watcher.file_watcher import FileWatcher as _BaseWatcher
from loguru import logger as _loguru_logger

from src.webui.logs_ws import log_broker

__all__ = ["FileWatcher"]

logger = get_logger(__name__)

_CORE_DIRS = {"core", "routes"}
_PLATFORM_DIR = "platforms"

# Key packages to monitor for version changes
_WATCHED_PACKAGES = ("echotools", "aiohttp", "pydantic")
_PACKAGE_CHECK_INTERVAL = 30.0  # seconds


def _classify(changed: Set[str]) -> Tuple[bool, Set[str], bool]:
    """Classify changed files as core (restart), platform (hot-reload), or frontend (browser refresh).

    Args:
        changed: Set of absolute file paths that changed.

    Returns:
        (needs_restart, platform_names, needs_frontend_reload):
            - needs_restart: whether a restart is required
            - platform_names: set of platform names that were changed
            - needs_frontend_reload: whether frontend files changed (browser refresh needed)
    """
    needs_restart = False
    platform_names: Set[str] = set()
    needs_frontend_reload = False

    for fp in changed:
        p = Path(fp)
        parts = p.parts

        if p.name in ("main_config.toml", "main.py"):
            needs_restart = True
            continue

        try:
            src_idx = parts.index("src")
        except ValueError:
            needs_restart = True
            continue

        sub_parts = parts[src_idx + 1 :]
        if not sub_parts:
            needs_restart = True
            continue

        first = sub_parts[0]

        if first in _CORE_DIRS or first == "__init__.py":
            needs_restart = True
        elif first == _PLATFORM_DIR and len(sub_parts) >= 2:
            platform_names.add(sub_parts[1])
        elif first == "webui" and len(sub_parts) >= 3 and sub_parts[1] == "static":
            # Frontend static files: src/webui/static/...
            needs_frontend_reload = True
        else:
            needs_restart = True

    return needs_restart, platform_names, needs_frontend_reload


def _trigger_restart(session: Any, registry: Any) -> None:
    """Trigger Worker process restart (exit code 42).

    Args:
        session: HTTP session object (attempt graceful close).
        registry: Registry object (attempt graceful close).
    """
    logger.info("Core file changed, preparing restart...")
    for resource in (session, registry):
        if resource:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(resource.close())
            except Exception as exc:
                logger.warning("Failed to close resource: %s", exc)
    os._exit(42)


class FileWatcher:
    """File change watcher — reuses echotools.FileWatcher + project classification logic.

    Watch logic:
    - Core files (``core/``, ``routes/``, ``config/main_config.toml``, ``main.py``) changed
      -> exit code 42 restart
    - Platform files (``src/platforms/<name>/``) changed
      -> hot-reload the platform, refresh candidates
    - Key package files (echotools, aiohttp, pydantic) changed
      -> exit code 42 restart
    """

    # Minimum seconds between consecutive frontend reload broadcasts
    _FRONTEND_RELOAD_COOLDOWN = 5.0

    def __init__(self, root: Path) -> None:
        """Initialize file watcher.

        Args:
            root: Project root directory path.
        """
        self._root = root
        self._registry: Optional[Any] = None
        self._session: Optional[Any] = None
        self._package_mtimes: Dict[str, float] = {}
        self._package_check_task: Optional[asyncio.Task] = None
        self._last_frontend_reload: float = 0.0

        paths = []
        src = root / "src"
        if src.is_dir():
            paths.append(src)
        for f in (root / "config" / "main_config.toml", root / "main.py"):
            if f.is_file():
                paths.append(f)

        self._watcher = _BaseWatcher(
            paths=paths,
            extensions={".py", ".toml", ".js", ".css", ".html"},
            interval=2.0,
        )

    def _snapshot_package_mtimes(self) -> None:
        """Record modification times of key package __init__.py files."""
        for pkg_name in _WATCHED_PACKAGES:
            try:
                spec = importlib.util.find_spec(pkg_name)
                if spec and spec.origin:
                    mtime = os.path.getmtime(spec.origin)
                    self._package_mtimes[pkg_name] = mtime
            except Exception:
                pass

    async def _check_package_versions(self) -> None:
        """Periodically check if key packages have been updated."""
        while True:
            await asyncio.sleep(_PACKAGE_CHECK_INTERVAL)
            for pkg_name, old_mtime in list(self._package_mtimes.items()):
                try:
                    spec = importlib.util.find_spec(pkg_name)
                    if spec and spec.origin:
                        new_mtime = os.path.getmtime(spec.origin)
                        if new_mtime != old_mtime:
                            logger.info(
                                "Package [%s] version changed, triggering restart",
                                pkg_name,
                            )
                            _trigger_restart(self._session, self._registry)
                            return
                except Exception:
                    pass

    async def _on_change(self, changed: Set[str]) -> None:
        """File change callback — classify and handle restart, hot-reload, or frontend refresh.

        Args:
            changed: Set of absolute file paths that changed.
        """
        logger.info("File change detected: %s", [Path(f).name for f in changed])

        needs_restart, platform_names, needs_frontend_reload = _classify(changed)

        if needs_restart:
            await asyncio.sleep(1.0)
            _trigger_restart(self._session, self._registry)
            return

        for name in platform_names:
            if self._registry and self._session:
                logger.info("Hot-reloading platform: %s", name)
                ok = await self._registry.reload_platform(name, self._session)
                if ok:
                    adapter = self._registry.adapters.get(name)
                    models = (
                        list(getattr(adapter, "supported_models", []))
                        if adapter
                        else []
                    )
                    for model in models:
                        try:
                            await self._registry.ensure_candidates(model, 1)
                        except Exception as exc:
                            logger.warning("Candidate refresh failed: %s", exc)
                else:
                    logger.warning("Platform [%s] hot-reload failed", name)

        if needs_frontend_reload:
            logger.info("Frontend files changed, broadcasting reload to browsers")
            try:
                await log_broker.broadcast({"type": "reload"})
            except Exception as exc:
                logger.warning("Failed to broadcast reload: %s", exc)

    async def start(self, registry: Any, session: Any) -> None:
        """Start file watcher.

        Args:
            registry: Registry object (for hot-reloading platforms).
            session: HTTP session object (for requests during hot-reload).
        """
        self._registry = registry
        self._session = session
        self._snapshot_package_mtimes()
        self._package_check_task = asyncio.create_task(self._check_package_versions())
        await self._watcher.start(self._on_change)
        logger.info("File watcher started: %s", self._root)

    def stop(self) -> None:
        """Stop file watcher."""
        if self._package_check_task and not self._package_check_task.done():
            self._package_check_task.cancel()
        self._watcher.stop()
        logger.info("File watcher stopped")
