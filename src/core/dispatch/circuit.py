
import time
from collections import deque
from dataclasses import dataclass, field
from threading import Lock
from typing import Deque, Dict, Optional

from src.foundation.config import get_config
from src.foundation.config.secs import CircuitCfg

__all__ = ["PlatformCircuitBreaker", "get_platform_circuit_breaker"]

_record_lock = Lock()


@dataclass
class _PlatformWindow:
    outcomes: Deque[bool] = field(default_factory=lambda: deque(maxlen=20))
    opened_at: float = 0.0


class PlatformCircuitBreaker:
    """按平台滑动窗口统计成功率，低于阈值时临时 open。"""

    def __init__(self) -> None:
        self._windows: Dict[str, _PlatformWindow] = {}
        self._lock = Lock()

    def _cfg(self) -> CircuitCfg:
        return get_config().circuit

    def _window(self, platform: str) -> _PlatformWindow:
        with self._lock:
            win = self._windows.get(platform)
            if win is None:
                win = _PlatformWindow()
                self._windows[platform] = win
            return win

    def allow_platform(self, platform: str) -> bool:
        cfg = self._cfg()
        if not cfg.enabled or not platform:
            return True
        win = self._window(platform)
        if win.opened_at <= 0:
            return True
        if time.time() - win.opened_at >= cfg.cooldown_seconds:
            win.opened_at = 0.0
            win.outcomes.clear()
            return True
        return False

    def record(self, platform: str, success: bool) -> None:
        cfg = self._cfg()
        if not cfg.enabled or not platform:
            return
        win = self._window(platform)
        with self._lock:
            win.outcomes.append(success)
            if win.opened_at > 0:
                return
            if len(win.outcomes) < max(3, cfg.window_size // 2):
                return
            fails = sum(1 for ok in win.outcomes if not ok)
            rate = fails / len(win.outcomes)
            if len(win.outcomes) >= cfg.window_size and rate >= cfg.failure_threshold:
                win.opened_at = time.time()

    def status(self, platform: str) -> str:
        if not self.allow_platform(platform):
            return "open"
        return "closed"

    def all_statuses(self) -> Dict[str, str]:
        with self._lock:
            names = list(self._windows.keys())
        return {name: self.status(name) for name in names}


_breaker: Optional[PlatformCircuitBreaker] = None


def get_platform_circuit_breaker() -> PlatformCircuitBreaker:
    global _breaker
    if _breaker is None:
        _breaker = PlatformCircuitBreaker()
    return _breaker
