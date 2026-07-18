# -*- coding: utf-8 -*-
from __future__ import annotations

"""插件 load / unload / reload 生命周期（从 PluginRuntime 分离）。"""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Tuple

from src.core.server.plugins.plugin_catalog import (
    find_plugin_dir_by_id,
    is_plugin_enabled,
)
from src.foundation.logger import get_logger

if TYPE_CHECKING:
    from src.core.server.plugins.runtime import PluginRuntime

__all__ = ["PluginLifecycle"]

logger = get_logger(__name__)


class PluginLifecycle:
    """封装单插件与平台插件的热加载生命周期。"""

    def __init__(self, runtime: PluginRuntime) -> None:
        self._rt = runtime

    def find_plugin_record(
        self, plugin_id: str
    ) -> Optional[Tuple[Any, Any, str]]:
        for ptype, loader in self._rt._loaders.items():
            record = loader.loaded_plugins.get(plugin_id)
            if record is not None:
                return loader, record, ptype
        return None

    def find_platform_record(
        self, platform_name: str
    ) -> Optional[Tuple[Any, Any, str]]:
        loader = self._rt._loaders.get("platform")
        if loader is None:
            return None
        for plugin_id, record in loader.loaded_plugins.items():
            adapter = record.adapter
            if adapter is not None and getattr(adapter, "name", "") == platform_name:
                return loader, record, plugin_id
        return None

    async def unload_plugin(self, plugin_id: str) -> bool:
        """卸载插件（on_unload + 模块清理），不重新加载。"""
        found = self.find_plugin_record(plugin_id)
        if found is None:
            return False
        loader, record, _ptype = found

        if record.adapter is not None:
            try:
                await record.adapter.close()
            except Exception as exc:
                logger.warning("关闭旧适配器 [%s] 失败: %s", plugin_id, exc)

        try:
            await record.plugin.on_unload()
        except Exception as exc:
            logger.warning("插件 on_unload 失败 [%s]: %s", plugin_id, exc)

        try:
            loader.purge_plugin_modules(plugin_id, record.plugin_dir)
        except Exception as exc:
            logger.warning("清理插件模块缓存失败 [%s]: %s", plugin_id, exc)

        loader.loaded_plugins.pop(plugin_id, None)
        self._rt._records.pop(plugin_id, None)
        self._rt._failed.pop(plugin_id, None)
        logger.info("插件已卸载: %s", plugin_id)
        self._rt._rebuild_hooks()
        return True

    async def load_plugin(self, plugin_dir: Path, session: Any) -> bool:
        """从目录加载单个启用中的插件。"""
        if not is_plugin_enabled(plugin_dir):
            return False
        try:
            from provider_sdk.runtime.loader import PluginLoader
            from provider_sdk.types.manifest import load_manifest_file
        except ImportError:
            return False

        manifest_path = plugin_dir / "_manifest.json"
        try:
            manifest = load_manifest_file(manifest_path)
        except Exception as exc:
            self._rt._record_failure(str(plugin_dir.name), str(exc))
            return False

        plugin_id = manifest.id
        if plugin_id in self._rt._records:
            return True

        ptype = str(manifest.plugin_type or "general")
        loader = self._rt._primary_loader()
        if loader is None:
            loader = PluginLoader(
                host_version=self._rt._host_version(), plugin_type_filter=""
            )
            self._rt._loaders[""] = loader
        self._rt._loaders.setdefault(ptype, loader)

        try:
            new_record = await loader._load_one(  # noqa: SLF001
                plugin_dir,
                manifest,
                session,
            )
        except Exception as exc:
            self._rt._record_failure(plugin_id, str(exc))
            logger.error("插件加载失败 [%s]: %s", plugin_id, exc)
            return False

        loader.loaded_plugins[plugin_id] = new_record
        self._rt._records[plugin_id] = new_record
        self._rt._failed.pop(plugin_id, None)
        logger.info("插件已加载: %s", plugin_id)
        self._rt._rebuild_hooks()
        return True

    async def reload_plugin(self, plugin_id: str, session: Any) -> bool:
        """热重载单个插件（on_unload → 清模块缓存 → on_load）。"""
        found = self.find_plugin_record(plugin_id)
        if found is None:
            return False
        loader, record, _ptype = found

        if record.adapter is not None:
            try:
                await record.adapter.close()
            except Exception as exc:
                logger.warning("关闭旧适配器 [%s] 失败: %s", plugin_id, exc)

        try:
            await record.plugin.on_unload()
        except Exception as exc:
            logger.warning("插件 on_unload 失败 [%s]: %s", plugin_id, exc)

        try:
            loader.purge_plugin_modules(plugin_id, record.plugin_dir)
        except Exception as exc:
            logger.warning("清理插件模块缓存失败 [%s]: %s", plugin_id, exc)

        loader.loaded_plugins.pop(plugin_id, None)
        self._rt._records.pop(plugin_id, None)

        try:
            new_record = await loader._load_one(  # noqa: SLF001
                record.plugin_dir,
                record.manifest,
                session,
            )
        except Exception as exc:
            self._rt._record_failure(plugin_id, str(exc))
            logger.error("插件热重载失败 [%s]: %s", plugin_id, exc)
            return False

        loader.loaded_plugins[plugin_id] = new_record
        self._rt._records[plugin_id] = new_record
        self._rt._failed.pop(plugin_id, None)
        logger.info("插件已热重载: %s", plugin_id)
        self._rt._rebuild_hooks()
        return True

    async def sync_plugin_manifest(self, plugin_id: str, session: Any) -> str:
        """根据磁盘 manifest 状态同步插件：load / unload / reload。"""
        plugin_dir = find_plugin_dir_by_id(plugin_id)
        if plugin_dir is None:
            return "missing"

        enabled = is_plugin_enabled(plugin_dir)
        loaded = plugin_id in self._rt._records

        if enabled and not loaded:
            return "loaded" if await self.load_plugin(plugin_dir, session) else "failed"
        if not enabled and loaded:
            return "unloaded" if await self.unload_plugin(plugin_id) else "failed"
        if enabled and loaded:
            return "reloaded" if await self.reload_plugin(plugin_id, session) else "failed"
        return "unchanged"

    async def reload_platform(self, platform_name: str, session: Any) -> Optional[Any]:
        """热重载单个平台插件适配器。"""
        found = self.find_platform_record(platform_name)
        if found is None:
            return None
        _loader, _record, plugin_id = found
        ok = await self.reload_plugin(plugin_id, session)
        if not ok:
            return None
        new_record = self._rt._records.get(plugin_id)
        if new_record is None:
            return None
        logger.info("平台插件已热重载: %s", platform_name)
        return new_record.adapter
