from __future__ import annotations

"""请求统计收集器 — 使用 echotools 通用实现，带服务端持久化。"""

import json
import threading

from echotools.web.stats import RequestStats, get_stats
from src.logger import get_logger
from src.paths import persist_json_dir

__all__ = ["RequestStats", "get_stats", "save_stats", "load_stats", "start_persist"]

_log = get_logger(__name__)

_PERSIST_FILE = persist_json_dir() / "stats.json"
_persist_timer: threading.Timer | None = None
_PERSIST_INTERVAL = 30  # seconds


def save_stats() -> None:
    """Persist current stats snapshot to disk."""
    try:
        persist_json_dir()  # ensure exists
        data = get_stats().to_dict()
        _PERSIST_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        _log.debug("Failed to persist stats", exc_info=True)


def load_stats() -> None:
    """Restore stats from persisted file on startup."""
    try:
        if _PERSIST_FILE.exists():
            raw = _PERSIST_FILE.read_text(encoding="utf-8")
            data = json.loads(raw)
            if isinstance(data, dict):
                get_stats().restore(data)
                _log.debug("Stats restored from %s", _PERSIST_FILE)
    except Exception:
        _log.debug("Failed to restore stats", exc_info=True)


def _persist_loop() -> None:
    """Periodic save triggered by a timer thread."""
    global _persist_timer
    try:
        save_stats()
    except Exception:
        pass
    _persist_timer = threading.Timer(_PERSIST_INTERVAL, _persist_loop)
    _persist_timer.daemon = True
    _persist_timer.start()


def start_persist() -> None:
    """Start the periodic persistence loop. Call once at app startup."""
    global _persist_timer
    if _persist_timer is not None:
        return  # already started
    load_stats()
    _persist_loop()
