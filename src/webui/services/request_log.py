"""WebUI 请求日志存储 — 使用 echotools 通用实现，带服务端持久化。"""

import json
import logging
import threading
from pathlib import Path

from echotools.web.broker import RequestBroker, request_broker

__all__ = ["RequestBroker", "request_broker", "save_requests", "load_requests", "start_request_persist"]

_log = logging.getLogger(__name__)

_PERSIST_DIR = Path(__file__).resolve().parent.parent.parent.parent / "persist" / "webui"
_PERSIST_FILE = _PERSIST_DIR / "requests.json"
_persist_timer: threading.Timer | None = None
_PERSIST_INTERVAL = 30  # seconds
_MAX_PERSIST = 200  # max entries to persist


def save_requests() -> None:
    """Persist recent request log entries to disk."""
    try:
        _PERSIST_DIR.mkdir(parents=True, exist_ok=True)
        items = request_broker.get_recent(_MAX_PERSIST)
        _PERSIST_FILE.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    except Exception:
        _log.debug("Failed to persist request log", exc_info=True)


def load_requests() -> None:
    """Restore request log from persisted file on startup."""
    try:
        if _PERSIST_FILE.exists():
            raw = _PERSIST_FILE.read_text(encoding="utf-8")
            items = json.loads(raw)
            if isinstance(items, list):
                for entry in items:
                    if isinstance(entry, dict):
                        request_broker._buffer.append(entry)
                _log.info("Request log restored %d entries from %s", len(items), _PERSIST_FILE)
    except Exception:
        _log.debug("Failed to restore request log", exc_info=True)


def _persist_loop() -> None:
    """Periodic save triggered by a timer thread."""
    global _persist_timer
    try:
        save_requests()
    except (OSError, json.JSONDecodeError):
        _log.debug("Failed in request persist loop", exc_info=True)
    except Exception:
        _log.warning("Unexpected error in request persist loop", exc_info=True)
    _persist_timer = threading.Timer(_PERSIST_INTERVAL, _persist_loop)
    _persist_timer.daemon = True
    _persist_timer.start()


def start_request_persist() -> None:
    """Start the periodic persistence loop. Call once at app startup."""
    global _persist_timer
    if _persist_timer is not None:
        return  # already started
    load_requests()
    _persist_loop()
