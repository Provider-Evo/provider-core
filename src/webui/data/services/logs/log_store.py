from __future__ import annotations

"""WebUI 请求日志 SQLite 持久化——数据库层。

提供 SQLite 初始化、批量写入、定时刷盘、记录裁剪等同步操作。
被 request_log.py（主模块）和 request_log_query.py（查询模块）引用。
"""

import json
import sqlite3
import threading
from pathlib import Path
from typing import List

from src.foundation.logger import get_logger
from src.foundation.paths import persist_db_dir

_log = get_logger(__name__)

# ------------------------------------------------------------------
# SQLite 配置
# ------------------------------------------------------------------

_DB_PATH = persist_db_dir() / "requests.db"
_MAX_ENTRIES = 5000    # 数据库最多保留条数
_MAX_BUFFER = 200      # 内存 buffer 最大条数
MAX_QUERY_LIMIT = 500  # REST 查询单次最大条数

_FLUSH_INTERVAL = 10   # 批量写入间隔（秒）
_FLUSH_BATCH = 20      # 脏数据达到此数量时立即刷盘

_MAX_COLUMN_BYTES = 32 * 1024

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
-- 基础索引
CREATE INDEX IF NOT EXISTS idx_request_ts ON request_logs(ts);
CREATE INDEX IF NOT EXISTS idx_request_model ON request_logs(model);
CREATE INDEX IF NOT EXISTS idx_request_platform ON request_logs(platform);
CREATE INDEX IF NOT EXISTS idx_request_status ON request_logs(status);
-- 复合索引：优化常见查询模式
CREATE INDEX IF NOT EXISTS idx_request_ts_model ON request_logs(ts, model);
CREATE INDEX IF NOT EXISTS idx_request_ts_platform ON request_logs(ts, platform);
CREATE INDEX IF NOT EXISTS idx_request_model_platform ON request_logs(model, platform);
CREATE INDEX IF NOT EXISTS idx_request_ts_status ON request_logs(ts, status);
"""

# ------------------------------------------------------------------
# 脏数据缓冲 + 锁
# ------------------------------------------------------------------

_dirty: List[dict] = []
_lock = threading.Lock()
_flush_timer: threading.Timer | None = None
_started = False


def clamp_query_limit(limit: int) -> int:
    """将分页 limit 限制在 1..MAX_QUERY_LIMIT。"""
    try:
        value = int(limit)
    except (TypeError, ValueError):
        value = 50
    return max(1, min(value, MAX_QUERY_LIMIT))


def _truncate_column(value: str, limit: int = _MAX_COLUMN_BYTES) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


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
