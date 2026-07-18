"""Provider-Evo 统一插件运行时（容错式加载）。"""
from __future__ import annotations

import time
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple

from src.foundation.logger import get_logger
from src.foundation.paths import project_root
from src.core.server.plugins.hook_reg import get_hook_registry
from src.core.server.plugins.plugin_lifecycle import PluginLifecycle

__all__ = ["PluginRuntime", "get_plugin_runtime"]

logger = get_logger(__name__)

_runtime: Optional["PluginRuntime"] = None

_FAILURE_RING_MAX = 50


class PluginRuntime:
    """扫描 plugins/ 并加载 fncall / platform / webui / coplan 插件。

    容错策略：
    - 单插件加载失败仅记录，不阻断同类型其他插件
    - 单类型全部失败不阻断其他类型插件
    - 全部插件失败也不 raise，网关仍可启动
    - 启动结束输出汇总日志：loaded / failed / inactive
    """

    def __init__(self) -> None:
        self._loaders: Dict[str, Any] = {}
        self._records: Dict[str, Any] = {}
        self._failed: Dict[str, str] = {}
        self._failure_ring: Deque[Tuple[str, str, float]] = deque(maxlen=_FAILURE_RING_MAX)
        self._inactive_count = 0
        self._plugins_root = project_root / "plugins"
        self._lifecycle = PluginLifecycle(self)

    @property
    def failed_plugins(self) -> Dict[str, str]:
        out = dict(self._failed)
        for loader in self._loaders.values():
            out.update(getattr(loader, "failed_plugins", {}))
        return out

    @property
    def loaded(self) -> Dict[str, Any]:
        return dict(self._records)

    def _record_failure(self, plugin_id: str, reason: str) -> None:
        self._failed[plugin_id] = reason
        self._failure_ring.append((plugin_id, reason, time.time()))

    def get_recent_failures(self) -> List[Dict[str, Any]]:
        """返回最近 N 条插件失败记录（环形缓冲）。"""
        return [
            {"plugin_id": pid, "reason": reason, "ts": ts}
            for pid, reason, ts in self._failure_ring
        ]

    def _host_version(self) -> str:
        try:
            from src.foundation.config import get_config

            return str(get_config().server.version or "")
        except Exception:
            return ""

    def _primary_loader(self) -> Any | None:
        loader = self._loaders.get("")
        if loader is not None:
            return loader
        for candidate in self._loaders.values():
            return candidate
        return None

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
        if not self._plugins_root.is_dir():
            logger.warning("plugins/ 目录不存在，跳过插件加载")
            return
        try:
            from provider_sdk.runtime.loader import PluginLoader
        except ImportError:
            logger.error("provider-sdk 未安装，无法加载插件")
            self._record_failure("provider-sdk", "provider-sdk 未安装，无法加载插件")
            return

        host_ver = self._host_version()
        loaded_count = 0
        failed_count = 0
        self._inactive_count = self._count_inactive_manifests()

        try:
            loader = PluginLoader(host_version=host_ver, plugin_type_filter="")
            loaded = await loader.discover_and_load(self._plugins_root, session)
            self._loaders[""] = loader
            for rec in loaded:
                ptype = str(rec.manifest.plugin_type or "general")
                self._loaders.setdefault(ptype, loader)
                self._records[rec.manifest.id] = rec
                loaded_count += 1
                logger.info(
                    "插件已加载 [%s] %s v%s",
                    ptype,
                    rec.manifest.id,
                    rec.manifest.version,
                )
            for pid, reason in loader.failed_plugins.items():
                self._record_failure(pid, reason)
                failed_count += 1
                logger.error("插件加载失败 [%s]: %s", pid, reason)
        except Exception as exc:
            logger.error("插件加载异常: %s", exc)
            failed_count += 1

        logger.info(
            "插件初始化完成: loaded=%d failed=%d inactive=%d",
            loaded_count,
            failed_count,
            self._inactive_count,
        )
        self._rebuild_hooks()
        self._inject_plugin_configs()

    def _inject_plugin_configs(self) -> None:
        """自动注入插件配置：读取 config.toml → set_plugin_config()。

        对每个已声明 ``config_model`` 的插件，自动从插件目录读取
        config.toml 并调用 SDK 的 ``set_plugin_config()`` 注入配置。
        插件可在 ``on_load()`` 中通过 ``self.config`` 访问注入后的配置。
        """
        from src.foundation.config.reader import get_config_reader

        reader = get_config_reader()
        for pid, rec in self._records.items():
            plugin = rec.plugin
            has_model = getattr(type(plugin), "has_config_model", lambda: False)()
            if not has_model:
                continue
            plugin_dir = getattr(rec, "plugin_dir", None)
            if plugin_dir is None:
                continue
            from pathlib import Path as _P
            pdir = _P(plugin_dir)
            config, _schema, _raw = reader.get_plugin_config(pdir)
            if not config:
                continue
            try:
                plugin.set_plugin_config(config)
                logger.debug("已注入插件配置: %s", pid)
            except Exception as exc:
                logger.warning("插件配置注入失败 [%s]: %s", pid, exc)

    def _rebuild_hooks(self) -> None:
        try:
            get_hook_registry().rebuild_from_runtime(self)
        except Exception as exc:
            logger.warning("Hook 注册表重建失败: %s", exc)

    async def unload_plugin(self, plugin_id: str) -> bool:
        return await self._lifecycle.unload_plugin(plugin_id)

    async def load_plugin(self, plugin_dir: Path, session: Any) -> bool:
        return await self._lifecycle.load_plugin(plugin_dir, session)

    async def sync_plugin_manifest(self, plugin_id: str, session: Any) -> str:
        return await self._lifecycle.sync_plugin_manifest(plugin_id, session)

    async def reload_plugin(self, plugin_id: str, session: Any) -> bool:
        return await self._lifecycle.reload_plugin(plugin_id, session)

    async def reload_platform(self, platform_name: str, session: Any) -> Optional[Any]:
        return await self._lifecycle.reload_platform(platform_name, session)

    async def close(self) -> None:
        seen: set[int] = set()
        for loader in self._loaders.values():
            loader_id = id(loader)
            if loader_id in seen:
                continue
            seen.add(loader_id)
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
        self._add_disabled_statuses(statuses)
        return statuses

    def _add_disabled_statuses(self, statuses: Dict[str, str]) -> None:
        """辅助函数：添加禁用插件的状态。"""
        if not self._plugins_root.is_dir():
            return
        for child in self._plugins_root.iterdir():
            if not child.is_dir():
                continue
            manifest = child / "_manifest.json"
            disabled = child / "_manifest.json.disabled"
            if disabled.is_file() and not manifest.is_file():
                self._try_set_disabled_status(statuses, disabled)

    def _try_set_disabled_status(
        self, statuses: Dict[str, str], disabled_path: Path
    ) -> None:
        """尝试从禁用manifest中读取plugin_id并设置disabled状态。"""
        try:
            import json

            data = json.loads(disabled_path.read_text(encoding="utf-8"))
            pid = str(data.get("id", ""))
            if pid:
                statuses[pid] = "disabled"
        except Exception:
            pass


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
