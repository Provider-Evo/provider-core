from __future__ import annotations

"""ModelsCache — 复用 echotools ListCache，保持原始 API 兼容。"""

from pathlib import Path
from typing import List

from echotools.cache.list_cache import ListCache

__all__ = ["ModelsCache", "models"]

_PERSIST_ROOT = Path(__file__).parent.parent.parent / "persist"


class ModelsCache(ListCache):
    """模型缓存 — 包装 ListCache，保持原始 ModelsCache API。"""

    def __init__(
        self,
        platform: str,
        fallback_models: List[str],
        fetch_enabled: bool = True,
    ) -> None:
        super().__init__(
            name=platform,
            fallback=fallback_models,
            cache_path=str(_PERSIST_ROOT / platform / "models.json"),
            overwrite=fetch_enabled,
            data_key="models",
        )

    @property
    def models(self) -> List[str]:
        """当前模型列表（兼容原始 API）。"""
        return self.items


_cache = None


def models() -> ModelsCache:
    """获取全局 ModelsCache 单例。"""
    global _cache
    if _cache is None:
        _cache = ModelsCache("", [])
    return _cache
