"""WebUI 请求日志 SQLite 持久化。

将请求日志写入 ``persist/webui/db/requests.db``，替代旧的 JSON 文件持久化。
启动时从 SQLite 加载最近 N 条到内存 buffer，供 WebSocket 推送使用。

数据流
------

::

  middleware.push_event(request_end)
    → RequestBroker.broadcast()  [内存 buffer + WebSocket 广播]
    → _patched_broadcast()       [同时写入 SQLite dirty list]
    → _flush_timer               [每 10 秒批量写入 SQLite]

架构
----

- **内存层**: ``RequestBroker._buffer`` (deque, maxlen=200) 供 WebSocket 实时推送
- **持久层**: SQLite ``request_logs`` 表，最多保留 5000 条
- **写入**: monkey-patch ``RequestBroker.broadcast()``，拦截 ``request_end`` 事件
- **批量刷盘**: 脏数据达到 20 条或每 10 秒定时刷盘
- **启动恢复**: 从 SQLite 加载最近 200 条到内存 buffer

SQLite Schema
-------------

.. code-block:: sql

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

公共 API
--------

- ``start_request_persist()`` — 启动持久化（app 启动时调用一次）
- ``query_requests(limit, model, platform, status, since)`` — 从 SQLite 查询
- ``get_request_count()`` — 返回总记录数
- ``load_requests()`` — 从 SQLite 加载到内存 buffer
- ``save_requests()`` — 兼容旧接口，触发 flush
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, List

from echotools.web.broker import RequestBroker, request_broker
from src.logger import get_logger

__all__ = [
    "RequestBroker", "request_broker",
    "save_requests", "load_requests", "start_request_persist",
]

_log = get_logger(__name__)

# ------------------------------------------------------------------
# SQLite 配置
# ------------------------------------------------------------------

_PERSIST_DIR = Path(__file__).resolve().parent.parent.parent.parent / "persist" / "webui"
_DB_DIR = _PERSIST_DIR / "db"
_JSON_DIR = _PERSIST_DIR / "json"
_DB_PATH = _DB_DIR / "requests.db"
_MAX_ENTRIES = 5000   # 数据库最多保留条数
_MAX_BUFFER = 200     # 内存 buffer 最大条数
_FLUSH_INTERVAL = 10  # 批量写入间隔（秒）
_FLUSH_BATCH = 20     # 脏数据达到此数量时立即刷盘

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
    _PERSIST_DIR.mkdir(parents=True, exist_ok=True)
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
                    json.dumps(e.get("messages", []), ensure_ascii=False),
                    1 if e.get("has_tools") else 0,
                    1 if e.get("stream") else 0,
                    e.get("response", ""),
                )
                for e in items
            ],
        )
        conn.commit()
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
                entry: dict[str, Any] = {
                    "type": "request_end",
                    "id": data["id"],
                    "ts": data["ts"],
                    "model": data["model"],
                    "platform": data["platform"],
                    "status": data["status"],
                    "latency_ms": data["latency_ms"],
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
# Monkey-patch RequestBroker.broadcast 以拦截 request_end 事件
# ------------------------------------------------------------------

_orig_broadcast = RequestBroker.broadcast


async def _patched_broadcast(self: RequestBroker, payload: dict) -> None:
    """包装 broadcast：在 request_end 时同时写入脏列表。"""
    await _orig_broadcast(self, payload)
    if payload.get("type") == "request_end":
        # 合并 request_start 的信息（messages 等）
        req_id = payload.get("id", "")
        start_data = self._active.get(req_id, {})
        entry = dict(payload)
        for key in ("messages", "messages_count", "has_tools", "stream"):
            if key in start_data:
                entry[key] = start_data[key]
        with _lock:
            _dirty.append(entry)
            if len(_dirty) >= _FLUSH_BATCH:
                threading.Thread(target=_flush, daemon=True).start()


# ------------------------------------------------------------------
# 启动入口
# ------------------------------------------------------------------

def start_request_persist() -> None:
    """启动请求日志持久化。在 app 启动时调用一次。"""
    global _started, _flush_timer
    if _started:
        return
    _started = True

    _init_db()

    # 清理旧 JSON 文件（迁移遗留）
    old_json = _PERSIST_DIR / "requests.json"
    if old_json.exists():
        try:
            _migrate_json(old_json)
            old_json.unlink()
            _log.info("Migrated legacy requests.json to SQLite and removed it")
        except Exception:
            _log.debug("Failed to migrate legacy requests.json", exc_info=True)

    load_requests()

    RequestBroker.broadcast = _patched_broadcast  # type: ignore[assignment]

    _flush_loop()

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
# 兼容旧接口
# ------------------------------------------------------------------

def save_requests() -> None:
    """兼容旧接口，实际调用 _flush()。"""
    _flush()


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
