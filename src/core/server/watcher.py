"""文件监视 — 复用 echotools FileWatcher + 项目特有分类/重启逻辑。"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, Optional, Set

from echotools.logger.manager import get_logger
from echotools.watcher.file_watcher import FileWatcher as _BaseWatcher

__all__ = ["FileWatcher"]
logger = get_logger(__name__)

_CORE_DIRS = {"core", "routes"}
_PLATFORM_DIR = "platforms"


def _classify(changed: Set[str]) -> tuple:
    """分类变更文件为核心文件或平台文件。"""
    needs_restart = False
    platform_names: Set[str] = set()
    for fp in changed:
        p = Path(fp)
        parts = p.parts
        if p.name in ("config.toml", "main.py"):
            needs_restart = True
            continue
        try:
            src_idx = parts.index("src")
        except ValueError:
            needs_restart = True
            continue
        sub_parts = parts[src_idx + 1:]
        if not sub_parts:
            needs_restart = True
            continue
        first = sub_parts[0]
        if first in _CORE_DIRS or first == "__init__.py":
            needs_restart = True
        elif first == _PLATFORM_DIR and len(sub_parts) >= 2:
            platform_names.add(sub_parts[1])
        else:
            needs_restart = True
    return needs_restart, platform_names


def _trigger_restart(session: Any, registry: Any) -> None:
    logger.info("核心文件变更，准备触发重启...")
    for resource in (session, registry):
        if resource:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(resource.close())
            except Exception as exc:
                logger.warning("关闭资源失败: %s", exc)
    os._exit(42)


class FileWatcher:
    """文件变更监视器 — 复用 echotools FileWatcher + 项目分类逻辑。"""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._registry: Optional[Any] = None
        self._session: Optional[Any] = None
        paths = []
        src = root / "src"
        if src.is_dir():
            paths.append(src)
        for f in (root / "config.toml", root / "main.py"):
            if f.is_file():
                paths.append(f)
        self._watcher = _BaseWatcher(paths=paths, extensions={".py", ".toml"}, interval=2.0)

    async def _on_change(self, changed: Set[str]) -> None:
        logger.info("检测到文件变更: %s", [Path(f).name for f in changed])
        needs_restart, platform_names = _classify(changed)
        if needs_restart:
            await asyncio.sleep(1.0)
            _trigger_restart(self._session, self._registry)
            return
        for name in platform_names:
            if self._registry and self._session:
                logger.info("热重载平台: %s", name)
                ok = await self._registry.reload_platform(name, self._session)
                if ok:
                    adapter = self._registry._adapters.get(name)
                    for model in list(getattr(adapter, "supported_models", [])) if adapter else []:
                        try:
                            await self._registry.ensure_candidates(model, 1)
                        except Exception as e:
                            logger.warning("候选项刷新失败: %s", e)
                else:
                    logger.warning("平台 [%s] 热重载失败", name)

    async def start(self, registry: Any, session: Any) -> None:
        self._registry = registry
        self._session = session
        await self._watcher.start(self._on_change)
        logger.info("文件监视已启动: %s", self._root)

    def stop(self) -> None:
        self._watcher.stop()
        logger.info("文件监视已停止")
