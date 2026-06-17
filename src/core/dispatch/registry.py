"""平台注册表 — 复用 echotools PluginRegistry，绑定 PlatformAdapter。"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from echotools.logger.manager import get_logger
from echotools.plugin.registry import PluginRegistry

from src.core.config import get_config
from src.core.dispatch.candidate import Candidate
from src.core.dispatch.selector import Selector

__all__ = ["Registry"]
logger = get_logger(__name__)

_PERSIST_ROOT = Path(__file__).parent.parent.parent.parent / "persist"


class Registry:
    """平台注册表 — 复用 echotools PluginRegistry。"""

    def __init__(self) -> None:
        self._registry = PluginRegistry()
        self.selector = Selector(persist_dir=str(_PERSIST_ROOT / "gateway"), group_attr="platform")

    async def init(self, session: Any) -> None:
        cfg = get_config()
        plat_cfg = cfg.platforms_cfg
        wl = plat_cfg.platform_list if plat_cfg.platform_list_type == "whitelist" else None
        bl = plat_cfg.platform_list if plat_cfg.platform_list_type == "blacklist" else None
        from src.platforms.base import PlatformAdapter
        await self._registry.discover_and_register(
            "src.platforms",
            context=session,
            whitelist=wl,
            blacklist=bl,
            base_class=PlatformAdapter,
            required_methods=("init", "candidates", "ensure_candidates", "complete", "close"),
            init_method="init",
            shutdown_method="close",
        )

    async def reload_platform(self, platform_name: str, session: Any) -> bool:
        from src.platforms.base import PlatformAdapter  # noqa: PLC0415
        return await self._registry.reload(
            platform_name,
            "src.platforms.{}".format(platform_name),
            context=session,
            base_class=PlatformAdapter,
            required_methods=("init", "candidates", "ensure_candidates", "complete", "close"),
            init_method="init",
            shutdown_method="close",
        )

    @property
    def adapters(self) -> Dict[str, Any]:
        return self._registry.plugins

    async def get_candidates(self, model: Optional[str] = None, capability: Optional[str] = None) -> List[Candidate]:
        def _filter(c: Any) -> bool:
            if not getattr(c, "available", True) or getattr(c, "busy", False):
                return False
            if model is not None and model not in getattr(c, "models", []):
                return False
            if capability is not None and not getattr(c, "has_capability", lambda _: False)(capability):
                return False
            return True
        return await self._registry.collect_from_all("candidates", filter_fn=_filter)

    async def ensure_candidates(self, model: str, count: int) -> None:
        for a in self._registry.plugins.values():
            if model in getattr(a, "supported_models", []):
                try:
                    await a.ensure_candidates(count)
                except Exception as exc:
                    logger.warning("[%s] ensure_candidates 失败: %s", getattr(a, "name", "?"), exc)

    def adapter_for(self, c: Candidate) -> Optional[Any]:
        return self._registry.get(c.platform)

    async def get_capable_adapter(self, capability: str) -> Optional[Any]:
        return self._registry.get_by_capability(capability)

    async def get_capable_candidate(self, capability: str) -> Optional[Candidate]:
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
        return await self.all_models()

    async def close(self) -> None:
        await self._registry.close()
