
import time
from collections import deque
from dataclasses import dataclass, field
from threading import Lock
from typing import Deque, Dict, Optional, Tuple

from src.foundation.config import get_config

__all__ = ["RateLimiter", "get_rate_limiter"]


@dataclass
class _Bucket:
    hits: Deque[float] = field(default_factory=deque)


class RateLimiter:
    def __init__(self) -> None:
        self._buckets: Dict[str, _Bucket] = {}
        self._lock = Lock()

    def _bucket(self, key: str) -> _Bucket:
        with self._lock:
            b = self._buckets.get(key)
            if b is None:
                b = _Bucket()
                self._buckets[key] = b
            return b

    @staticmethod
    def _prune(bucket: _Bucket, window_sec: float, now: float) -> None:
        cutoff = now - window_sec
        while bucket.hits and bucket.hits[0] < cutoff:
            bucket.hits.popleft()

    def allow(
        self, scope: str, limit: int, window_sec: float = 60.0
    ) -> Tuple[bool, int]:
        """返回 (allowed, retry_after_seconds)。"""
        if limit <= 0:
            return True, 0
        now = time.time()
        bucket = self._bucket(scope)
        with self._lock:
            self._prune(bucket, window_sec, now)
            if len(bucket.hits) >= limit:
                retry = max(1, int(window_sec - (now - bucket.hits[0])))
                return False, retry
            bucket.hits.append(now)
            return True, 0

    def check_request(self, key_scope: str, ip_scope: str) -> Tuple[bool, int]:
        cfg = get_config().rate_limit
        if not cfg.enabled:
            return True, 0
        ok, retry = self.allow("key:" + key_scope, cfg.key_rpm)
        if not ok:
            return False, retry
        return self.allow("ip:" + ip_scope, cfg.ip_rpm)


_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter()
    return _limiter
