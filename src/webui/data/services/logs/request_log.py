from __future__ import annotations

"""WebUI 请求日志 SQLite 持久化。

替代旧的 JSON 文件持久化，将请求日志写入 ``persist/webui/requests.db``。
启动时从 SQLite 加载最近 N 条到内存 buffer，供 WebSocket 推送使用。

数据流：
  middleware.push_event(request_end)
    → RequestBroker.broadcast()  [内存 buffer + WebSocket 广播]
    → _patched_broadcast()       [同时写入 SQLite dirty list]
    → _flush_timer               [每 10 秒批量写入 SQLite]
"""

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, List

from echotools.web.broker import RequestBroker, request_broker

from src.foundation.logger import get_logger
from src.foundation.paths import persist_db_dir, persist_dir, persist_json_dir

__all__ = [
    "RequestBroker",
    "clamp_query_limit",
    "load_requests",
    "prepare_request_log_reload",
    "request_broker",
    "save_requests",
    "start_request_persist",
]

_DEFAULT_QUERY_LIMIT = 50
_MAX_QUERY_LIMIT = 200


def clamp_query_limit(raw: Any, default: int = _DEFAULT_QUERY_LIMIT) -> int:
    """将 REST 查询 limit 规范到合法正整数区间。"""
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    if value < 1:
        return default
    return min(value, _MAX_QUERY_LIMIT)

_log = get_logger(__name__)

# ------------------------------------------------------------------
# SQLite 配置
# ------------------------------------------------------------------

_DB_PATH = persist_db_dir() / "requests.db"
_MAX_ENTRIES = 5000   # 数据库最多保留条数
_MAX_BUFFER = 200     # 内存 buffer 最大条数
_FLUSH_INTERVAL = 10  # 批量写入间隔（秒）
_FLUSH_BATCH = 20     # 脏数据达到此数量时立即刷盘

_MAX_COLUMN_BYTES = 32 * 1024


def _truncate_column(value: str, limit: int = _MAX_COLUMN_BYTES) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


_DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS request_logs (
    id TEXT PRIMARY KEY,
    ts REAL NOT NULL,
    model TEXT DEFAULT '',
    platform TEXT DEFAULT '',
    status INTEGER DEFAULT 0,
    latency_ms REAL DEFAULT 0.0,
    messages_count INTEGER DEFAULT 0,
    messages TEXT DEFAULT '[]',
    has_tools INTEGER DEFAULT 0,
    stream INTEGER DEFAULT 0,
    response TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_request_ts ON request_logs(ts);
CREATE INDEX IF NOT EXISTS idx_request_model ON request_logs(model);
CREATE INDEX IF NOT EXISTS idx_request_platform ON request_logs(platform);
CREATE INDEX IF NOT EXISTS idx_request_status ON request_logs(status);
"""

# ------------------------------------------------------------------
# 脏数据缓冲 + 锁
# ------------------------------------------------------------------

_dirty: List[dict] = []
_lock = threading.Lock()
_flush_timer: threading.Timer | None = None
_started = False


# ------------------------------------------------------------------
# 数据库操作
# ------------------------------------------------------------------

def _init_db() -> None:
    """创建 SQLite 数据库和表结构。"""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    try:
        conn.executescript(_DB_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def _flush() -> None:
    """将脏数据批量写入 SQLite。"""
    with _lock:
        if not _dirty:
            return
        items = list(_dirty)
        _dirty.clear()

    conn = sqlite3.connect(str(_DB_PATH))
    try:
        conn.executemany(
            """INSERT OR REPLACE INTO request_logs
               (id, ts, model, platform, status, latency_ms,
                messages_count, messages, has_tools, stream, response)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    e.get("id", ""),
                    e.get("ts", 0.0),
                    e.get("model", ""),
                    e.get("platform", ""),
                    e.get("status", 0),
                    e.get("latency_ms", 0.0),
                    e.get("messages_count", 0),
                    json.dumps(e.get("messages", []), ensure_ascii=False)[:_MAX_COLUMN_BYTES],
                    1 if e.get("has_tools") else 0,
                    1 if e.get("stream") else 0,
                    _truncate_column(str(e.get("response", ""))),
                )
                for e in items
            ],
        )
        conn.commit()
        _prune_old()
    except Exception:
        _log.warning("Failed to flush request logs to SQLite", exc_info=True)
    finally:
        conn.close()


def _flush_loop() -> None:
    """定时刷盘循环。"""
    global _flush_timer
    try:
        _flush()
    except Exception:
        _log.debug("Flush loop error", exc_info=True)
    _flush_timer = threading.Timer(_FLUSH_INTERVAL, _flush_loop)
    _flush_timer.daemon = True
    _flush_timer.start()


def _prune_old() -> None:
    """删除超出上限的旧记录。"""
    conn = sqlite3.connect(str(_DB_PATH))
    try:
        conn.execute(
            """DELETE FROM request_logs WHERE id NOT IN
               (SELECT id FROM request_logs ORDER BY ts DESC LIMIT ?)""",
            (_MAX_ENTRIES,),
        )
        conn.commit()
    except Exception:
        _log.debug("Prune failed", exc_info=True)
    finally:
        conn.close()


# ------------------------------------------------------------------
# 读取
# ------------------------------------------------------------------

def load_requests() -> None:
    """从 SQLite 加载最近 N 条到内存 buffer。"""
    if not _DB_PATH.exists():
        return
    try:
        conn = sqlite3.connect(str(_DB_PATH))
        try:
            cursor = conn.execute(
                "SELECT * FROM request_logs ORDER BY ts DESC LIMIT ?",
                (_MAX_BUFFER,),
            )
            columns = [desc[0] for desc in cursor.description]
            count = 0
            for row in cursor:
                data = dict(zip(columns, row))
                # 还原为 WebSocket 推送格式
                messages_raw = data.get("messages") or "[]"
                try:
                    messages = json.loads(messages_raw)
                except (json.JSONDecodeError, TypeError):
                    messages = []
                entry: dict[str, Any] = {
                    "type": "request_end",
                    "id": data["id"],
                    "ts": data["ts"],
                    "model": data["model"],
                    "platform": data["platform"],
                    "status": data["status"],
                    "latency_ms": data["latency_ms"],
                    "messages_count": data.get("messages_count", 0),
                    "messages": messages,
                    "has_tools": bool(data.get("has_tools")),
                    "stream": bool(data.get("stream")),
                    "response": data.get("response") or "",
                }
                request_broker._buffer.append(entry)
                count += 1
            if count:
                _log.debug("Restored %d request logs from SQLite", count)
        finally:
            conn.close()
    except Exception:
        _log.debug("Failed to restore request logs", exc_info=True)


def get_request_count() -> int:
    """返回数据库中的总记录数。"""
    if not _DB_PATH.exists():
        return 0
    try:
        conn = sqlite3.connect(str(_DB_PATH))
        try:
            return conn.execute("SELECT COUNT(*) FROM request_logs").fetchone()[0]
        finally:
            conn.close()
    except Exception:
        return 0


# ------------------------------------------------------------------
# 响应内容缓冲（在 push_event 同步路径聚合，避免 request_end 先于 chunk 到达）
# ------------------------------------------------------------------

_response_buffers: dict[str, list[str]] = {}


def _accumulate_request_event(payload: dict[str, Any]) -> dict[str, Any]:
    """在调度 broadcast 前同步聚合响应文本，并为 request_end 补充 response 字段。"""
    event_type = payload.get("type")
    req_id = str(payload.get("id", ""))

    if event_type == "request_start":
        if req_id:
            _response_buffers[req_id] = []
        return payload

    if event_type == "request_chunk":
        delta = payload.get("delta", "")
        if req_id and delta:
            _response_buffers.setdefault(req_id, []).append(str(delta))
        return payload

    if event_type != "request_end" or not req_id:
        return payload

    buffered = "".join(_response_buffers.pop(req_id, []))
    response = str(payload.get("response") or buffered)
    if not response:
        return payload

    enriched = dict(payload)
    enriched["response"] = response
    return enriched


_ORIG_PUSH_EVENT = None
_ORIG_BROADCAST = None


def _install_broker_hooks() -> None:
    global _ORIG_PUSH_EVENT, _ORIG_BROADCAST
    if _ORIG_PUSH_EVENT is None:
        _ORIG_PUSH_EVENT = RequestBroker.push_event
    if _ORIG_BROADCAST is None:
        _ORIG_BROADCAST = RequestBroker.broadcast
    RequestBroker.push_event = _patched_push_event  # type: ignore[assignment]
    RequestBroker.broadcast = _patched_broadcast  # type: ignore[assignment]


def _uninstall_broker_hooks() -> None:
    if _ORIG_PUSH_EVENT is not None:
        RequestBroker.push_event = _ORIG_PUSH_EVENT  # type: ignore[assignment]
    if _ORIG_BROADCAST is not None:
        RequestBroker.broadcast = _ORIG_BROADCAST  # type: ignore[assignment]


def _patched_push_event(self: RequestBroker, payload: dict[str, Any]) -> None:
    _ORIG_PUSH_EVENT(self, _accumulate_request_event(payload))


# ------------------------------------------------------------------
# Monkey-patch RequestBroker.broadcast 以拦截 request_end 事件
# ------------------------------------------------------------------

_REQUEST_END_MERGE_KEYS = (
    "ts",
    "messages",
    "messages_count",
    "has_tools",
    "stream",
    "model",
    "platform",
)


def _is_empty_merge_value(key: str, value: Any) -> bool:
    if value is None:
        return True
    if key == "ts":
        return not value
    if key == "messages_count":
        return value == 0
    if key == "messages":
        return value == []
    if key in ("model", "platform"):
        return value == ""
    return False


def _enrich_request_end(payload: dict[str, Any], start_data: dict[str, Any]) -> dict[str, Any]:
    """Merge request_start metadata into request_end before buffer/WS broadcast."""
    enriched = dict(payload)
    for key in _REQUEST_END_MERGE_KEYS:
        if key not in start_data:
            continue
        start_val = start_data[key]
        if key in ("has_tools", "stream"):
            if start_val and not enriched.get(key):
                enriched[key] = start_val
            continue
        if key not in enriched or _is_empty_merge_value(key, enriched.get(key)):
            enriched[key] = start_val
    if "ts" not in enriched or _is_empty_merge_value("ts", enriched.get("ts")):
        enriched["ts"] = start_data.get("ts") or time.time()
    return enriched


async def _patched_broadcast(self: RequestBroker, payload: dict) -> None:
    """包装 broadcast：在 request_end 时同时写入脏列表。"""
    outbound = payload
    start_data: dict[str, Any] = {}
    if payload.get("type") == "request_end":
        req_id = str(payload.get("id", ""))
        start_data = dict(self._active.get(req_id, {}))
        outbound = _enrich_request_end(payload, start_data)

    await _ORIG_BROADCAST(self, outbound)

    if payload.get("type") == "request_end":
        req_id = str(payload.get("id", ""))
        entry = dict(outbound)
        if not entry.get("response"):
            buffered = "".join(_response_buffers.pop(req_id, []))
            if buffered:
                entry["response"] = buffered
        with _lock:
            _dirty.append(entry)
            if len(_dirty) >= _FLUSH_BATCH:
                threading.Thread(target=_flush, daemon=True).start()


# ------------------------------------------------------------------
# 启动入口
# ------------------------------------------------------------------



def prepare_request_log_reload() -> None:
    """L3 热重载前刷盘、卸载钩子并清空内存 buffer。"""
    global _started, _flush_timer
    _flush()
    if _flush_timer is not None:
        _flush_timer.cancel()
        _flush_timer = None
    _uninstall_broker_hooks()
    request_broker._buffer.clear()
    request_broker._active.clear()
    _response_buffers.clear()
    with _lock:
        _dirty.clear()
    _started = False

async def start_request_persist() -> None:
    """启动请求日志持久化。在 app 启动时调用一次。"""
    global _started, _flush_timer
    if _started:
        return
    _started = True

    _init_db()

    # 清理旧 JSON 文件（迁移遗留）
    old_json = persist_json_dir() / "requests.json"
    if not old_json.exists():
        old_json = persist_dir("webui") / "requests.json"  # 兼容旧路径
    if old_json.exists():
        try:
            _migrate_json(old_json)
            old_json.unlink()
            _log.info("Migrated legacy requests.json to SQLite and removed it")
        except Exception:
            _log.debug("Failed to migrate legacy requests.json", exc_info=True)

    # 加载历史
    load_requests()

    _install_broker_hooks()

    # 启动定时刷盘
    _flush_loop()

    # 注册退出时刷盘
    import atexit
    atexit.register(_flush)

    _log.info("Request log SQLite persistence started (db=%s)", _DB_PATH)


def _migrate_json(path: Path) -> None:
    """将旧 JSON 文件迁移到 SQLite。"""
    raw = path.read_text(encoding="utf-8")
    items = json.loads(raw)
    if not isinstance(items, list):
        return

    conn = sqlite3.connect(str(_DB_PATH))
    try:
        conn.executescript(_DB_SCHEMA)
        rows = []
        for e in items:
            if not isinstance(e, dict) or "id" not in e:
                continue
            rows.append((
                e.get("id", ""),
                e.get("ts", 0.0),
                e.get("model", ""),
                e.get("platform", ""),
                e.get("status", 0),
                e.get("latency_ms", 0.0),
                e.get("messages_count", 0),
                json.dumps(e.get("messages", []), ensure_ascii=False),
                1 if e.get("has_tools") else 0,
                1 if e.get("stream") else 0,
                e.get("response", ""),
            ))
        if rows:
            conn.executemany(
                """INSERT OR REPLACE INTO request_logs
                   (id, ts, model, platform, status, latency_ms,
                    messages_count, messages, has_tools, stream, response)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
            conn.commit()
            _log.info("Migrated %d entries from requests.json", len(rows))
    finally:
        conn.close()


# ------------------------------------------------------------------
# 兼容旧接口（被 stats.py 等引用）
# ------------------------------------------------------------------

def save_requests() -> None:
    """兼容旧接口，实际调用 _flush()。"""
    _flush()


# 导出给 stats.py 使用的 requests_list
def query_requests(
    limit: int = 50,
    model: str = "",
    platform: str = "",
    status: int | None = None,
    since: float = 0.0,
) -> list[dict]:
    """从 SQLite 查询请求日志，支持筛选。"""
    if not _DB_PATH.exists():
        return []

    conditions = []
    params: list = []

    if model:
        conditions.append("model = ?")
        params.append(model)
    if platform:
        conditions.append("platform = ?")
        params.append(platform)
    if status is not None:
        conditions.append("status = ?")
        params.append(status)
    if since > 0:
        conditions.append("ts >= ?")
        params.append(since)

    where = " AND ".join(conditions) if conditions else "1=1"
    sql = f"SELECT * FROM request_logs WHERE {where} ORDER BY ts DESC LIMIT ?"
    params.append(limit)

    conn = sqlite3.connect(str(_DB_PATH))
    try:
        cursor = conn.execute(sql, params)
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor]
    finally:
        conn.close()
