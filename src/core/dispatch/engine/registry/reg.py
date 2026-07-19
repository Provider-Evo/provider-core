"""平台注册表 — 复用 echotools PluginRegistry，绑定 PlatformAdapter。"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional, Tuple

from echotools.plugin.registry import PluginRegistry

from src.core.dispatch.cand import Candidate
from src.core.dispatch.engine.registry.reg_life import RegistryLifecycleMixin
from src.core.dispatch.engine.registry.reg_mod import RegistryModelsMixin
from src.core.dispatch.engine.selector import Selector
from src.foundation.logger import get_logger
from src.foundation.paths import persist_dir

__all__ = ["Registry"]
logger = get_logger(__name__)

_CANDIDATES_CACHE_TTL = 1.5


class Registry(RegistryLifecycleMixin, RegistryModelsMixin):
    """平台注册表 — 复用 echotools PluginRegistry。"""

    def __init__(self) -> None:
        self._registry = PluginRegistry()
        self.selector = Selector(
            persist_dir=str(persist_dir("gateway")), group_attr="platform"
        )
        self._external_loader: Any = None
        self._app_host: Any = None
        self._candidates_cache: Dict[str, Tuple[float, List[Candidate]]] = {}

    def _invalidate_candidates_cache(self) -> None:
        self._candidates_cache.clear()

    def set_app_host(self, app_host: Any) -> None:
        """绑定 AppHost，插件热重载后用于重建主站路由。"""
        self._app_host = app_host

    @property
    def adapters(self) -> Dict[str, Any]:
        """公开方法 adapters。"""
        return self._registry.plugins

    async def get_candidates(
        self, model: Optional[str] = None, capability: Optional[str] = None
    ) -> List[Candidate]:
        """公开方法 get_candidates。"""
        if model is not None and capability is None:
            cached = self._candidates_cache.get(model)
            if cached is not None:
                cached_at, items = cached
                if time.monotonic() - cached_at < _CANDIDATES_CACHE_TTL:
                    return list(items)

        def _filter(c: Candidate) -> bool:
            if not c.available or c.busy:
                return False
            meta = c.meta
            if isinstance(meta, dict) and meta.get("is_login") is False:
                return False
            if model is not None and model not in c.models:
                return False
            if capability is not None and not c.has_capability(capability):
                return False
            return True

        result = await self._registry.collect_from_all("candidates", filter_fn=_filter)
        if model is not None and capability is None:
            self._candidates_cache[model] = (time.monotonic(), result)
        return result

    async def ensure_candidates(self, model: str, count: int) -> None:
        """公开方法 ensure_candidates。"""
        for a in self._registry.plugins.values():
            if model in a.supported_models:
                try:
                    await a.ensure_candidates(count)
                except Exception as exc:
                    logger.warning("[%s] ensure_candidates 失败: %s", a.name, exc)

    def adapter_for(self, c: Candidate) -> Optional[Any]:
        """公开方法 adapter_for。"""
        return self._registry.get(c.platform)

    async def get_capable_adapter(self, capability: str) -> Optional[Any]:
        """公开方法 get_capable_adapter。"""
        return self._registry.get_by_capability(capability)

    async def get_capable_candidate(self, capability: str) -> Optional[Candidate]:
        """公开方法 get_capable_candidate。"""
        cands = await self.get_candidates(capability=capability)
        if cands:
            selected = await self.selector.select(cands, 1)
            if selected:
                return selected[0]
        return None

    async def close(self) -> None:
        """公开方法 close。"""
        if self._external_loader is not None:
            try:
                await self._external_loader.close()
            except Exception as exc:
                logger.warning("插件运行时关闭失败: %s", exc)
            self._external_loader = None

        # 保存适配器引用，PluginRegistry.close() 会清空 plugins 字典
        adapters = dict(self._registry.plugins)

        # 逐个适配器显式关闭，确保内部 session 被释放
        # PluginRegistry.close() 有5秒超时，可能未完全关闭
        for name, adapter in adapters.items():
            try:
                await asyncio.wait_for(adapter.close(), timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("适配器 [%s] 关闭超时", name)
            except Exception as exc:
                logger.warning("适配器 [%s] 关闭失败: %s", name, exc)

        # 清理 PluginRegistry 内部状态
        self._registry._plugins.clear()
        self._invalidate_candidates_cache()
