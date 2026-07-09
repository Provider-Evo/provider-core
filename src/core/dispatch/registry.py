"""平台注册表 — 复用 echotools PluginRegistry，绑定 PlatformAdapter。"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Sequence

from src.logger import get_logger
from echotools.plugin.registry import PluginRegistry

from src.core.config import get_config
from src.core.dispatch.candidate import Candidate
from src.core.dispatch.selector import Selector
from src.paths import persist_dir, project_root

__all__ = ["Registry"]
logger = get_logger(__name__)


class Registry:
    """平台注册表 — 复用 echotools PluginRegistry。"""

    def __init__(self) -> None:
        self._registry = PluginRegistry()
        self.selector = Selector(persist_dir=str(persist_dir("gateway")), group_attr="platform")
        self._external_loader: Any = None

    async def init(self, session: Any) -> None:
        """公开方法 init — 仅通过 plugins/ 加载平台适配器。

        容错：插件加载失败不向上抛出，网关仍可启动。
        """
        cfg = get_config()
        plat_cfg = cfg.platforms_cfg
        wl = plat_cfg.platform_list if plat_cfg.platform_list_type == "whitelist" else None
        bl = plat_cfg.platform_list if plat_cfg.platform_list_type == "blacklist" else None

        from src.core.plugins.runtime import get_plugin_runtime

        runtime = get_plugin_runtime()
        try:
            await runtime.init(session)
        except Exception as exc:
            logger.error("插件运行时初始化��常（网关继续启动）: %s", exc)
        self._external_loader = runtime

        adapter_count = 0
        for adapter in runtime.platform_adapters():
            name = getattr(adapter, "name", "")
            if not name:
                continue
            if wl is not None and name not in wl:
                continue
            if name in (bl or []):
                continue
            self._registry.register(adapter)
            adapter_count += 1
            logger.info("平台插件已注册: %s", name)

        if adapter_count == 0:
            logger.warning("0 个平台插件已注册，网关将以无平台模式运行")

    async def reload_platform(self, platform_name: str, session: Any) -> bool:
        """公开方法 reload_platform — 从插件路径重载平台适配器。"""
        from src.platforms.base import PlatformAdapter  # noqa: PLC0415

        # 优先从插件路径重载
        plugin_dir = project_root / "plugins" / f"Provider-{platform_name.capitalize()}-Adapter"
        if plugin_dir.is_dir():
            module_path = f"plugins.Provider-{platform_name.capitalize()}-Adapter.{platform_name}"
        else:
            # 回退到内置路径
            module_path = "src.platforms.{}".format(platform_name)

        return await self._registry.reload(
            platform_name,
            module_path,
            context=session,
            base_class=PlatformAdapter,
            required_methods=("init", "candidates", "ensure_candidates", "complete", "close"),
            init_method="init",
            shutdown_method="close",
        )

    async def reload_platforms(self, platform_names: Sequence[str], session: Any) -> None:
        """批量热重载平台适配器。"""
        for name in platform_names:
            ok = await self.reload_platform(name, session)
            if ok:
                adapter = self.adapters.get(name)
                models = (
                    list(getattr(adapter, "supported_models", []))
                    if adapter
                    else []
                )
                for model in models:
                    try:
                        await self.ensure_candidates(model, 1)
                    except Exception as exc:
                        logger.warning("候选项刷新失败: %s", exc)
            else:
                logger.warning("平台 [%s] 配置热重载失败", name)

    async def apply_config_reload(
        self,
        old_raw: Dict[str, Any],
        new_raw: Dict[str, Any],
        session: Any,
        scopes: Sequence[str],
    ) -> None:
        """配置热重载后更新平台运行时。"""
        from src.core.config.reload_policy import changed_platform_names

        scope_set = set(scopes)
        names = changed_platform_names(old_raw, new_raw)
        if names:
            await self.reload_platforms(sorted(names), session)
        if "platforms_cfg" in scope_set:
            await self.reload_platforms(sorted(self.adapters.keys()), session)

    @property
    def adapters(self) -> Dict[str, Any]:
        """公开方法 adapters。"""
        return self._registry.plugins

    async def get_candidates(self, model: Optional[str] = None, capability: Optional[str] = None) -> List[Candidate]:
        """公开方法 get_candidates。"""
        def _filter(c: Any) -> bool:
            if not getattr(c, "available", True) or getattr(c, "busy", False):
                return False
            meta = getattr(c, "meta", None)
            if isinstance(meta, dict) and meta.get("is_login") is False:
                return False
            if model is not None and model not in getattr(c, "models", []):
                return False
            if capability is not None and not getattr(c, "has_capability", lambda _: False)(capability):
                return False
            return True
        return await self._registry.collect_from_all("candidates", filter_fn=_filter)

    async def ensure_candidates(self, model: str, count: int) -> None:
        """公开方法 ensure_candidates。"""
        for a in self._registry.plugins.values():
            if model in getattr(a, "supported_models", []):
                try:
                    await a.ensure_candidates(count)
                except Exception as exc:
                    logger.warning("[%s] ensure_candidates 失败: %s", getattr(a, "name", "?"), exc)

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

    async def all_models(self) -> List[Dict[str, Any]]:
        """收集所有模型及其能力信息（/v1/models 格式）。"""
        import time
        out: List[Dict[str, Any]] = []
        seen: set = set()
        for a in self._registry.plugins.values():
            caps = getattr(a, "default_capabilities", {})
            ctx_len = getattr(a, "context_length", None)
            for m in getattr(a, "supported_models", []):
                if m not in seen:
                    seen.add(m)
                    entry: Dict[str, Any] = {
                        "id": m,
                        "object": "model",
                        "created": int(time.time()),
                        "owned_by": getattr(a, "name", ""),
                        "capabilities": dict(caps),
                    }
                    if ctx_len is not None:
                        entry["context_length"] = ctx_len
                    out.append(entry)
        return out

    async def list_models(self) -> List[Dict[str, Any]]:
        """公开方法 list_models。"""
        return await self.all_models()

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
                close_fn = getattr(adapter, "close", None)
                if close_fn is not None:
                    await asyncio.wait_for(close_fn(), timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("适配器 [%s] 关闭超时", name)
            except Exception as exc:
                logger.warning("适配器 [%s] 关闭失败: %s", name, exc)

        # 清理 PluginRegistry 内部状态
        self._registry._plugins.clear()
