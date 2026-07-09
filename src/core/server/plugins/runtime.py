"""Provider-Evo 统一插件运行时（容错式加载）。"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.core.server.plugins.sdk_compat import ensure_provider_sdk_platform_extras
from src.foundation.logger import get_logger
from src.foundation.paths import project_root
from src.core.server.plugins.hook_registry import get_hook_registry
from src.core.server.plugins.plugin_catalog import (
    find_plugin_dir_by_id,
    is_plugin_enabled,
)

__all__ = ["PluginRuntime", "get_plugin_runtime"]

logger = get_logger(__name__)

_runtime: Optional["PluginRuntime"] = None


class PluginRuntime:
    """扫描 plugins/ 并加载 fncall / platform / webui / coplan 插件。

    容错策略：
    - 单插件加载失败仅记录，不阻断同类型其他插件
    - 单类型全部失败不阻断其他类型插件
    - 全部插件失败也不 raise，网关仍可启动
    - 启动结束输出汇��日志：loaded / failed / inactive
    """

    def __init__(self) -> None:
        self._loaders: Dict[str, Any] = {}
        self._records: Dict[str, Any] = {}
        self._failed: Dict[str, str] = {}
        self._inactive_count = 0
        self._plugins_root = project_root / "plugins"

    @property
    def failed_plugins(self) -> Dict[str, str]:
        out = dict(self._failed)
        for loader in self._loaders.values():
            out.update(getattr(loader, "failed_plugins", {}))
        return out

    @property
    def loaded(self) -> Dict[str, Any]:
        return dict(self._records)

    def _host_version(self) -> str:
        try:
            from src.core.config import get_config

            return str(get_config().server.version or "")
        except Exception:
            return ""

    def _count_inactive_manifests(self) -> int:
        if not self._plugins_root.is_dir():
            return 0
        count = 0
        for child in self._plugins_root.iterdir():
            if not child.is_dir() or child.name.startswith("."):
                continue
            if (child / "_manifest.json.disabled").is_file() and not (
                child / "_manifest.json"
            ).is_file():
                count += 1
        return count

    async def init(self, session: Any) -> None:
        """初始化插件加载。容错：任意异常不向上抛出。"""
        ensure_provider_sdk_platform_extras()
        if not self._plugins_root.is_dir():
            logger.warning("plugins/ 目录不存在，跳过插件加载")
            return
        try:
            from provider_sdk.runtime.loader import PluginLoader
        except ImportError:
            logger.error("provider-sdk 未安装，无法加载插件")
            self._failed["provider-sdk"] = "provider-sdk 未安装，无法加载插件"
            return

        host_ver = self._host_version()
        loaded_count = 0
        failed_count = 0
        self._inactive_count = self._count_inactive_manifests()

        for ptype in ("fncall", "platform", "webui", "coplan", "general"):
            try:
                loader = PluginLoader(host_version=host_ver, plugin_type_filter=ptype)
                loaded = await loader.discover_and_load(self._plugins_root, session)
                self._loaders[ptype] = loader
                for rec in loaded:
                    self._records[rec.manifest.id] = rec
                    loaded_count += 1
                    logger.info(
                        "插件已加载 [%s] %s v%s",
                        ptype,
                        rec.manifest.id,
                        rec.manifest.version,
                    )
                # 记录该类型的失败插件
                for pid, reason in loader.failed_plugins.items():
                    self._failed[pid] = reason
                    failed_count += 1
                    logger.error("插件加载失败 [%s]: %s", pid, reason)
            except Exception as exc:
                # 单类型加载异常不阻断其他类型
                logger.error("插件类型 [%s] 加载异常: %s", ptype, exc)
                failed_count += 1

        # 启动汇总日志
        logger.info(
            "插件初始化完成: loaded=%d failed=%d inactive=%d",
            loaded_count,
            failed_count,
            self._inactive_count,
        )
        self._rebuild_hooks()

    def _rebuild_hooks(self) -> None:
        try:
            get_hook_registry().rebuild_from_runtime(self)
        except Exception as exc:
            logger.warning("Hook 注册表重建失败: %s", exc)

    async def unload_plugin(self, plugin_id: str) -> bool:
        """卸载插件（on_unload + 模块清理），不重新加载。"""
        found = self._find_plugin_record(plugin_id)
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
        self._records.pop(plugin_id, None)
        self._failed.pop(plugin_id, None)
        logger.info("插件已卸载: %s", plugin_id)
        self._rebuild_hooks()
        return True

    async def load_plugin(self, plugin_dir: Path, session: Any) -> bool:
        """从目录加载单个启用中的插件。"""
        ensure_provider_sdk_platform_extras()
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
            self._failed[str(plugin_dir.name)] = str(exc)
            return False

        plugin_id = manifest.id
        if plugin_id in self._records:
            return True

        ptype = str(manifest.plugin_type or "general")
        loader = self._loaders.get(ptype)
        if loader is None:
            loader = PluginLoader(
                host_version=self._host_version(),
                plugin_type_filter=ptype,
            )
            self._loaders[ptype] = loader

        try:
            new_record = await loader._load_one(  # noqa: SLF001
                plugin_dir,
                manifest,
                session,
            )
        except Exception as exc:
            self._failed[plugin_id] = str(exc)
            logger.error("插件加载失败 [%s]: %s", plugin_id, exc)
            return False

        loader.loaded_plugins[plugin_id] = new_record
        self._records[plugin_id] = new_record
        self._failed.pop(plugin_id, None)
        logger.info("插件已加载: %s", plugin_id)
        self._rebuild_hooks()
        return True

    async def sync_plugin_manifest(self, plugin_id: str, session: Any) -> str:
        """根据磁盘 manifest 状态同步插件：load / unload / reload。"""
        plugin_dir = find_plugin_dir_by_id(plugin_id)
        if plugin_dir is None:
            return "missing"

        enabled = is_plugin_enabled(plugin_dir)
        loaded = plugin_id in self._records

        if enabled and not loaded:
            return "loaded" if await self.load_plugin(plugin_dir, session) else "failed"
        if not enabled and loaded:
            return "unloaded" if await self.unload_plugin(plugin_id) else "failed"
        if enabled and loaded:
            return "reloaded" if await self.reload_plugin(plugin_id, session) else "failed"
        return "unchanged"

    def _find_platform_record(
        self, platform_name: str
    ) -> Optional[Tuple[Any, Any, str]]:
        loader = self._loaders.get("platform")
        if loader is None:
            return None
        for plugin_id, record in loader.loaded_plugins.items():
            adapter = record.adapter
            if adapter is not None and getattr(adapter, "name", "") == platform_name:
                return loader, record, plugin_id
        return None

    def _find_plugin_record(
        self, plugin_id: str
    ) -> Optional[Tuple[Any, Any, str]]:
        for ptype, loader in self._loaders.items():
            record = loader.loaded_plugins.get(plugin_id)
            if record is not None:
                return loader, record, ptype
        return None

    async def reload_plugin(self, plugin_id: str, session: Any) -> bool:
        """热重载单个插件（on_unload → 清模块缓存 → on_load）。"""
        ensure_provider_sdk_platform_extras()
        found = self._find_plugin_record(plugin_id)
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
        self._records.pop(plugin_id, None)

        try:
            new_record = await loader._load_one(  # noqa: SLF001
                record.plugin_dir,
                record.manifest,
                session,
            )
        except Exception as exc:
            self._failed[plugin_id] = str(exc)
            logger.error("插件热重载失败 [%s]: %s", plugin_id, exc)
            return False

        loader.loaded_plugins[plugin_id] = new_record
        self._records[plugin_id] = new_record
        self._failed.pop(plugin_id, None)
        logger.info("插件已热重载: %s", plugin_id)
        self._rebuild_hooks()
        return True

    async def reload_platform(self, platform_name: str, session: Any) -> Optional[Any]:
        """热重载单个平台插件适配器。"""
        found = self._find_platform_record(platform_name)
        if found is None:
            return None
        _loader, _record, plugin_id = found
        ok = await self.reload_plugin(plugin_id, session)
        if not ok:
            return None
        new_record = self._records.get(plugin_id)
        if new_record is None:
            return None
        logger.info("平台插件已热重载: %s", platform_name)
        return new_record.adapter

    async def close(self) -> None:
        for loader in self._loaders.values():
            try:
                await loader.unload_all()
            except Exception as exc:
                logger.warning("插件卸载失败: %s", exc)
        self._loaders.clear()
        self._records.clear()
        get_hook_registry().clear()

    def platform_adapters(self) -> List[Any]:
        adapters: List[Any] = []
        loader = self._loaders.get("platform")
        if loader is None:
            return adapters
        for rec in loader.loaded_plugins.values():
            if rec.adapter is not None:
                adapters.append(rec.adapter)
        return adapters

    def get_components(self, component_type: str | None = None) -> List[Dict[str, Any]]:
        """收集已加载插件声明的组件。"""
        out: List[Dict[str, Any]] = []
        for rec in self._records.values():
            for comp in rec.components:
                if component_type is None or comp.get("type") == component_type:
                    item = dict(comp)
                    item["plugin_id"] = rec.manifest.id
                    out.append(item)
        return out

    def get_load_statuses(self) -> Dict[str, str]:
        """返回所有插件的加载状态。"""
        statuses: Dict[str, str] = {}
        for rec in self._records.values():
            statuses[rec.manifest.id] = "loaded"
        for pid, reason in self.failed_plugins.items():
            if pid not in statuses:
                statuses[pid] = "failed"
        return statuses

    def get_plugin_load_failure_reasons(self) -> Dict[str, str]:
        """返回失败插件的原因。"""
        return dict(self.failed_plugins)

    def get_plugin_circuit_statuses(self) -> Dict[str, str]:
        """熔断状态：失败插件为 open，已加载为 closed，禁用为 disabled。"""
        statuses: Dict[str, str] = {}
        for rec in self._records.values():
            statuses[rec.manifest.id] = "closed"
        for pid in self.failed_plugins:
            if pid not in statuses:
                statuses[pid] = "open"
        if self._plugins_root.is_dir():
            for child in self._plugins_root.iterdir():
                if not child.is_dir():
                    continue
                manifest = child / "_manifest.json"
                disabled = child / "_manifest.json.disabled"
                if disabled.is_file() and not manifest.is_file():
                    try:
                        import json

                        data = json.loads(disabled.read_text(encoding="utf-8"))
                        pid = str(data.get("id", ""))
                        if pid:
                            statuses[pid] = "disabled"
                    except Exception:
                        pass
        return statuses

    def get_plugin_summary(self) -> Dict[str, int]:
        """返回插件加载汇总。"""
        loaded = len(self._records)
        failed = len(self.failed_plugins)
        return {
            "loaded": loaded,
            "failed": failed,
            "inactive": self._inactive_count,
        }


def get_plugin_runtime() -> PluginRuntime:
    global _runtime
    if _runtime is None:
        _runtime = PluginRuntime()
    return _runtime
