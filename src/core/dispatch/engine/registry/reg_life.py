"""平台注册表 — 插件加载/热重载生命周期管理。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from src.core.server.plugins.plugin_catalog import (
    find_plugin_dir_by_id,
    is_plugin_enabled,
)
from src.foundation.config import get_config
from src.foundation.logger import get_logger

__all__ = ["RegistryLifecycleMixin"]
logger = get_logger(__name__)


class RegistryLifecycleMixin:
    """插件加载、热重载与平台注册生命周期。"""

    def _platform_filters(self) -> "tuple[Optional[List[str]], Optional[List[str]]]":
        cfg = get_config()
        plat_cfg = cfg.platforms_cfg
        wl = (
            plat_cfg.platform_list
            if plat_cfg.platform_list_type == "whitelist"
            else None
        )
        bl = (
            plat_cfg.platform_list
            if plat_cfg.platform_list_type == "blacklist"
            else None
        )
        return wl, bl

    async def _maybe_reload_app(self) -> None:
        if self._app_host is None:
            return
        try:
            await self._app_host.reload_app()
        except RuntimeError as exc:
            if "尚未启动" in str(exc):
                logger.debug("AppHost 尚未启动，跳过应用重建")
            else:
                logger.warning("插件热重载后应用重建失败: %s", exc)
        except Exception as exc:
            logger.warning("插件热重载后应用重建失败: %s", exc)

    def _register_platform_adapter(self, adapter: Any) -> bool:
        wl, bl = self._platform_filters()
        name = adapter.name if hasattr(adapter, "name") else ""
        if not name:
            return False
        if wl is not None and name not in wl:
            return False
        if name in (bl or []):
            return False
        self._registry.register(adapter)
        logger.info("平台插件已注册: %s", name)
        return True

    async def _unregister_platform_adapter(self, platform_name: str) -> None:
        if not platform_name:
            return
        old = self._registry.get(platform_name)
        if old is None:
            return
        try:
            await old.close()
        except Exception as exc:
            logger.warning("关闭平台 [%s] 失败: %s", platform_name, exc)
        self._registry._plugins.pop(platform_name, None)
        self._invalidate_candidates_cache()

    def _plugin_runtime(self) -> Any:
        if self._external_loader is not None:
            return self._external_loader
        from src.core.server.plugins.runtime import get_plugin_runtime

        runtime = get_plugin_runtime()
        self._external_loader = runtime
        return runtime

    def _register_filtered_adapters(
        self, runtime: Any, wl: Optional[List[str]], bl: Optional[List[str]]
    ) -> int:
        adapter_count = 0
        for adapter in runtime.platform_adapters():
            name = adapter.name if hasattr(adapter, "name") else ""
            if not name:
                continue
            if wl is not None and name not in wl:
                continue
            if name in (bl or []):
                continue
            self._registry.register(adapter)
            adapter_count += 1
            logger.info("平台插件已注册: %s", name)
        return adapter_count

    async def init(self, session: Any) -> None:
        """仅通过 plugins/ 加载平台适配器。

        容错：插件加载失败不向上抛出，网关仍可启动。
        """
        wl, bl = self._platform_filters()

        from src.core.server.plugins.runtime import get_plugin_runtime

        runtime = get_plugin_runtime()
        try:
            await runtime.init(session)
        except Exception as exc:
            logger.error("插件运行时初始化异常（网关继续启动）: %s", exc)
        self._external_loader = runtime

        adapter_count = self._register_filtered_adapters(runtime, wl, bl)
        if adapter_count == 0:
            logger.warning("0 个平台插件已注册，网关将以无平台模式运行")

    async def _close_all_registered_adapters(self) -> None:
        for name, adapter in list(self._registry.plugins.items()):
            try:
                await adapter.close()
            except Exception as exc:
                logger.warning("关闭平台 [%s] 失败: %s", name, exc)
        self._registry._plugins.clear()
        self._invalidate_candidates_cache()

    async def _reacquire_plugin_runtime(self) -> Any:
        runtime = self._external_loader
        if runtime is None:
            from src.core.server.plugins.runtime import get_plugin_runtime

            runtime = get_plugin_runtime()
            self._external_loader = runtime
        else:
            try:
                await runtime.close()
            except Exception as exc:
                logger.warning("插件运行时关闭失败: %s", exc)
        return runtime

    async def reload_plugins(
        self, session: Any, *, reload_app: bool = True
    ) -> Dict[str, int]:
        """磁盘插件变更后全量热重载运行时与平台注册表。"""
        wl, bl = self._platform_filters()

        await self._close_all_registered_adapters()
        runtime = await self._reacquire_plugin_runtime()
        await runtime.init(session)

        adapter_count = self._register_filtered_adapters(runtime, wl, bl)

        summary = runtime.get_plugin_summary()
        logger.info(
            "插件热重载完成: platforms=%d loaded=%d failed=%d inactive=%d",
            adapter_count,
            summary.get("loaded", 0),
            summary.get("failed", 0),
            summary.get("inactive", 0),
        )
        if reload_app:
            await self._maybe_reload_app()
        return summary

    async def _reload_single_plugin_id(
        self,
        plugin_id: str,
        session: Any,
        runtime: Any,
        wl: Optional[List[str]],
        bl: Optional[List[str]],
    ) -> bool:
        from src.core.dispatch.engine.registry.reg_reload import reload_single_plugin_id

        return await reload_single_plugin_id(
            self._registry, plugin_id, session, runtime, wl, bl
        )

    async def reload_plugins_by_ids(
        self, plugin_ids: Sequence[str], session: Any, *, reload_app: bool = True
    ) -> Dict[str, int]:
        """按插件 ID 热重载（coplan / fncall / webui / platform 等）。"""
        runtime = self._plugin_runtime()
        wl, bl = self._platform_filters()

        attempted_ids: List[str] = []
        skipped_ids: List[str] = []

        for plugin_id in plugin_ids:
            plugin_dir = find_plugin_dir_by_id(plugin_id)
            if plugin_dir is None:
                logger.debug("插件热重载跳过（未知 id）: %s", plugin_id)
                skipped_ids.append(plugin_id)
                continue

            enabled = is_plugin_enabled(plugin_dir)
            loaded = plugin_id in runtime.loaded

            if not enabled and not loaded:
                logger.debug("插件热重载跳过（未启用且未加载）: %s", plugin_id)
                skipped_ids.append(plugin_id)
                continue

            if not enabled and loaded:
                await self.sync_plugin_manifest(plugin_id, session, reload_app=False)
                skipped_ids.append(plugin_id)
                continue

            attempted_ids.append(plugin_id)
            await self._reload_single_plugin_id(plugin_id, session, runtime, wl, bl)

        summary = runtime.get_plugin_summary()
        logger.info(
            "插件精确热重载完成: ids=%s skipped=%s app_reload=%s loaded=%d failed=%d",
            attempted_ids,
            skipped_ids,
            reload_app,
            summary.get("loaded", 0),
            summary.get("failed", 0),
        )
        if reload_app:
            await self._maybe_reload_app()
        return summary

    async def sync_plugin_manifest(
        self,
        plugin_id: str,
        session: Any,
        *,
        reload_app: bool = True,
    ) -> str:
        """manifest 启用/禁用或元数据变更时同步插件与平台注册表。"""
        runtime = self._plugin_runtime()
        record_before = runtime.loaded.get(plugin_id)
        platform_name = ""
        if record_before is not None and record_before.adapter is not None:
            platform_name = (
                record_before.adapter.name
                if hasattr(record_before.adapter, "name")
                else ""
            )

        action = await runtime.sync_plugin_manifest(plugin_id, session)
        logger.info("插件 manifest 同步 [%s]: %s", plugin_id, action)

        if action == "unloaded":
            await self._unregister_platform_adapter(platform_name)
        elif action in {"loaded", "reloaded"}:
            await self._apply_manifest_reload(plugin_id, runtime, platform_name)

        if reload_app and action in {"loaded", "reloaded", "unloaded"}:
            await self._maybe_reload_app()
        if action in {"loaded", "reloaded", "unloaded"}:
            self._invalidate_candidates_cache()
        return action

    async def _apply_manifest_reload(
        self, plugin_id: str, runtime: Any, platform_name: str
    ) -> None:
        record_after = runtime.loaded.get(plugin_id)
        if record_after is None or record_after.adapter is None:
            return
        new_name = (
            record_after.adapter.name if hasattr(record_after.adapter, "name") else ""
        )
        if platform_name and platform_name != new_name:
            await self._unregister_platform_adapter(platform_name)
        self._register_platform_adapter(record_after.adapter)
        adapter = record_after.adapter
        for model in (
            list(adapter.supported_models)
            if hasattr(adapter, "supported_models")
            else []
        ):
            try:
                await self.ensure_candidates(model, 1)
            except Exception as exc:
                logger.warning("候选项刷新失败 [%s]: %s", plugin_id, exc)

    async def reload_platform(self, platform_name: str, session: Any) -> bool:
        if self._external_loader is None:
            return False

        old = self._registry.get(platform_name)
        if old is not None:
            try:
                await old.close()
            except Exception as exc:
                logger.warning("关闭旧平台 [%s] 失败: %s", platform_name, exc)
            self._registry._plugins.pop(platform_name, None)

        adapter = await self._external_loader.reload_platform(platform_name, session)
        if adapter is None:
            logger.warning("平台 [%s] 插件热重载失败", platform_name)
            return False

        self._registry.register(adapter)
        self._invalidate_candidates_cache()
        logger.info("平台 [%s] 已热重载", platform_name)
        return True

    async def reload_platforms(
        self, platform_names: Sequence[str], session: Any
    ) -> None:
        """批量热重载平台适配器。"""
        for name in platform_names:
            ok = await self.reload_platform(name, session)
            if not ok:
                logger.warning("平台 [%s] 配置热重载失败", name)
                continue
            adapter = self.adapters.get(name)
            models = (
                list(adapter.supported_models)
                if adapter and hasattr(adapter, "supported_models")
                else []
            )
            for model in models:
                try:
                    await self.ensure_candidates(model, 1)
                except Exception as exc:
                    logger.warning("候选项刷新失败: %s", exc)

    async def apply_config_reload(
        self,
        old_raw: Dict[str, Any],
        new_raw: Dict[str, Any],
        session: Any,
        scopes: Sequence[str],
    ) -> None:
        """配置热重载后更新平台运行时。"""
        from src.foundation.config.reload_policy import changed_platform_names

        scope_set = set(scopes)
        names = changed_platform_names(old_raw, new_raw)
        if names:
            await self.reload_platforms(sorted(names), session)
        if "platforms_cfg" in scope_set:
            await self.reload_platforms(sorted(self.adapters.keys()), session)
