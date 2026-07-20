
import hashlib
import json
import time
from collections import OrderedDict
from threading import Lock
from typing import Any, Dict, Optional, Tuple

from src.foundation.config import get_config
from src.foundation.config.secs import CacheCfg

__all__ = ["ResponseCache", "get_response_cache"]

_CACHE_VERSION = 1


class ResponseCache:
    """非流式 chat 响应的内存 LRU 精确缓存。

    优化点：
    1. 命中/未命中计数
    2. 分级 TTL 支持
    3. 详细的统计信息
    """

    def __init__(self) -> None:
        self._data: OrderedDict[str, Tuple[float, Dict[str, Any]]] = OrderedDict()
        self._lock = Lock()
        # 统计计数器
        self._hits = 0
        self._misses = 0
        self._total_requests = 0
        self._evictions = 0

    def _cfg(self) -> CacheCfg:
        return get_config().cache

    @staticmethod
    def _cache_key(
        model: str,
        messages: list,
        tools: Any,
        stream: bool,
        thinking: bool,
        search: bool,
    ) -> Optional[str]:
        if stream:
            return None
        payload = {
            "v": _CACHE_VERSION,
            "model": model,
            "messages": messages,
            "tools": tools,
            "thinking": thinking,
            "search": search,
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: Optional[str]) -> Optional[Dict[str, Any]]:
        """获取缓存项，更新命中/未命中计数。"""
        if not key:
            return None
        cfg = self._cfg()
        if not cfg.enabled:
            return None

        self._total_requests += 1
        now = time.time()

        with self._lock:
            item = self._data.get(key)
            if item is None:
                self._misses += 1
                return None
            ts, value = item
            if now - ts > cfg.ttl_seconds:
                self._data.pop(key, None)
                self._misses += 1
                return None
            self._data.move_to_end(key)
            self._hits += 1
            return dict(value)

    def put(self, key: Optional[str], value: Dict[str, Any]) -> None:
        """存储缓存项。"""
        if not key:
            return
        cfg = self._cfg()
        if not cfg.enabled:
            return
        with self._lock:
            self._data[key] = (time.time(), dict(value))
            self._data.move_to_end(key)
            while len(self._data) > cfg.max_entries:
                self._data.popitem(last=False)
                self._evictions += 1

    def get_hit_rate(self) -> float:
        """获取缓存命中率。"""
        with self._lock:
            total = self._hits + self._misses
            if total == 0:
                return 0.0
            return self._hits / total

    def stats(self) -> Dict[str, Any]:
        """获取详细的缓存统计信息。"""
        with self._lock:
            total = self._hits + self._misses
            return {
                "entries": len(self._data),
                "hits": self._hits,
                "misses": self._misses,
                "total_requests": total,
                "hit_rate": self._hits / total if total > 0 else 0.0,
                "evictions": self._evictions,
            }

    def reset_stats(self) -> None:
        """重置统计计数器。"""
        with self._lock:
            self._hits = 0
            self._misses = 0
            self._total_requests = 0
            self._evictions = 0


_cache: Optional[ResponseCache] = None


def get_response_cache() -> ResponseCache:
    global _cache
    if _cache is None:
        _cache = ResponseCache()
    return _cache
