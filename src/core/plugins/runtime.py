"""Provider-Evo 统一插件运行时（容错式加载）。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.logger import get_logger
from src.paths import project_root

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

    async def init(self, session: Any) -> None:
        """初始化插件加载。容错：任意异常不向上抛出。"""
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
        inactive_count = 0

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
            inactive_count,
        )

    async def close(self) -> None:
        for loader in self._loaders.values():
            try:
                await loader.unload_all()
            except Exception as exc:
                logger.warning("插件卸载失败: %s", exc)
        self._loaders.clear()
        self._records.clear()

    def platform_adapters(self) -> List[Any]:
        adapters: List[Any] = []
        loader = self._loaders.get("platform")
        if loader is None:
            return adapters
        for rec in loader.loaded_plugins.values():
            if rec.adapter is not None:
                adapters.append(rec.adapter)
        return adapters

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

    def get_plugin_summary(self) -> Dict[str, int]:
        """返回插件加载汇总。"""
        loaded = len(self._records)
        failed = len(self.failed_plugins)
        return {"loaded": loaded, "failed": failed, "inactive": 0}


def get_plugin_runtime() -> PluginRuntime:
    global _runtime
    if _runtime is None:
        _runtime = PluginRuntime()
    return _runtime
