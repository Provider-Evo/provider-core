"""Selector with SQLite persistence and stale candidate pruning."""
from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Dict

from echotools.dispatch.selector import AdaptiveSelector as _BaseSelector
from echotools.dispatch.selector import TASRecord

from src.logger import get_logger

__all__ = ["Selector", "TASRecord"]

logger = get_logger(__name__)

_DEFAULT_PRUNE_DAYS = 30
_FLUSH_INTERVAL = 5.0

_DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id TEXT PRIMARY KEY,
    group_name TEXT DEFAULT '',
    n_success INTEGER DEFAULT 0,
    n_fails INTEGER DEFAULT 0,
    latency_sum REAL DEFAULT 0.0,
    latency_sum_sq REAL DEFAULT 0.0,
    n_latency_samples INTEGER DEFAULT 0,
    speed_sum REAL DEFAULT 0.0,
    speed_sum_sq REAL DEFAULT 0.0,
    n_speed_samples INTEGER DEFAULT 0,
    last_success REAL DEFAULT 0.0,
    last_used REAL DEFAULT 0.0,
    error_time REAL DEFAULT 0.0,
    n_calls INTEGER DEFAULT 0,
    updated_at REAL DEFAULT 0.0
);
CREATE INDEX IF NOT EXISTS idx_group ON records(group_name);
CREATE INDEX IF NOT EXISTS idx_updated ON records(updated_at);
"""


class Selector(_BaseSelector):
    """类 Selector。"""
    """AdaptiveSelector with SQLite persistence and stale candidate pruning.

    Replaces the default JSON file persistence with a single SQLite database,
    eliminating the overhead of thousands of individual file I/O operations.

    On initialization:
    1. Migrates any legacy JSON files to SQLite (if db does not exist).
    2. Loads all records from SQLite into the in-memory pool.
    3. Prunes stale candidates based on the configured threshold.
    4. Starts a background flush thread for batched writes.
    """

    def __init__(
        self,
        persist_dir: str = "persist/dispatch",
        group_attr: str = "group",
        prune_days: int = _DEFAULT_PRUNE_DAYS,
    ) -> None:
        """Initialize selector with SQLite persistence.

        Args:
            persist_dir: Persistence directory path.
            group_attr: Group attribute name on candidate objects.
            prune_days: Maximum age in days before a candidate record
                is considered stale.  Defaults to 30.
        """
        self._prune_days = prune_days
        self._db_path = Path(persist_dir) / "gateway.db"
        self._sqlite_dirty: Dict[str, TASRecord] = {}
        self._flush_interval = _FLUSH_INTERVAL
        self._lock = threading.Lock()
        self._closed = False

        # Ensure parent directory exists
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize SQLite schema
        self._init_db()

        # Migrate legacy JSON files if db was just created
        self._migrate_json_if_needed()

        # Call parent __init__, which triggers _load()
        super().__init__(persist_dir=persist_dir, group_attr=group_attr)

        # Prune stale records
        self.prune_stale()

        # Start background flush thread
        self._start_flush_thread()

    # ------------------------------------------------------------------
    # Database initialization
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        """Create the SQLite database and schema if they don't exist."""
        conn = sqlite3.connect(str(self._db_path))
        try:
            conn.executescript(_DB_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # JSON → SQLite migration
    # ------------------------------------------------------------------

    def _migrate_json_if_needed(self) -> None:
        """Migrate legacy JSON files to SQLite if the database is empty."""
        if not self._db_path.exists():
            return

        # Check if db already has records
        conn = sqlite3.connect(str(self._db_path))
        try:
            count = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
            if count > 0:
                return
        finally:
            conn.close()

        # No records in db — try to migrate from JSON files
        json_files = list(self._db_path.parent.glob("*.json"))
        if not json_files:
            return

        logger.info("Migrating %d legacy JSON files to SQLite", len(json_files))
        migrated = 0

        conn = sqlite3.connect(str(self._db_path))
        try:
            for f in json_files:
                if f.name.startswith("_"):
                    continue
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    key = f.stem

                    # Handle both old EMA format and new summary format
                    record = self._convert_legacy_data(data)
                    if record is None:
                        continue

                    conn.execute(
                        """INSERT OR REPLACE INTO records
                           (id, group_name, n_success, n_fails, latency_sum,
                            latency_sum_sq, n_latency_samples, speed_sum,
                            speed_sum_sq, n_speed_samples, last_success,
                            last_used, error_time, n_calls, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (key, record.group, record.n_success, record.n_fails,
                         record.latency_sum, record.latency_sum_sq,
                         record.n_latency_samples, record.speed_sum,
                         record.speed_sum_sq, record.n_speed_samples,
                         record.last_success, record.last_used,
                         record.error_time, record.n_calls, time.time()),
                    )
                    migrated += 1
                except Exception as e:
                    logger.debug("Failed to migrate %s: %s", f.name, e)

            conn.commit()
        finally:
            conn.close()

        if migrated:
            logger.info("Successfully migrated %d records to SQLite", migrated)

        # Clean up legacy JSON files
        self._cleanup_json_files()

    def _convert_legacy_data(self, data: dict) -> TASRecord | None:
        """Convert legacy JSON data to a TASRecord.

        Handles both old EMA format (ema_speed, ema_latency, last_call)
        and new summary format (latency_sum, speed_sum, etc.).

        Old EMA fields cannot be precisely converted to summary statistics,
        so they are discarded and the record starts fresh.
        """
        # Skip corrupted files (e.g., terminal output mixed in)
        if "group" not in data:
            return None

        n_calls = data.get("n_calls", 0)
        n_fails = data.get("n_fails", 0)

        # If the file has the new summary format fields, use them directly
        if "latency_sum" in data or "speed_sum" in data:
            return TASRecord(
                group=data.get("group", ""),
                n_success=max(0, n_calls - n_fails),
                n_fails=n_fails,
                latency_sum=data.get("latency_sum", 0.0),
                latency_sum_sq=data.get("latency_sum_sq", 0.0),
                n_latency_samples=data.get("n_latency_samples", 0),
                speed_sum=data.get("speed_sum", 0.0),
                speed_sum_sq=data.get("speed_sum_sq", 0.0),
                n_speed_samples=data.get("n_speed_samples", 0),
                last_success=data.get("last_success", 0.0),
                last_used=data.get("last_used", 0.0),
                error_time=data.get("error_time", 0.0),
                n_calls=n_calls,
            )

        # Old EMA format: preserve basic metadata, discard imprecise stats
        return TASRecord(
            group=data.get("group", ""),
            n_success=max(0, n_calls - n_fails),
            n_fails=n_fails,
            error_time=data.get("error_time", 0.0),
            last_used=data.get("last_call", 0.0),
            n_calls=n_calls,
        )

    def _cleanup_json_files(self) -> None:
        """Remove legacy JSON files after migration."""
        persist_dir = self._db_path.parent
        if not persist_dir.exists():
            return

        json_files = list(persist_dir.glob("*.json"))
        if not json_files:
            return

        removed = 0
        for f in json_files:
            try:
                f.unlink()
                removed += 1
            except Exception as e:
                logger.debug("Failed to delete %s: %s", f.name, e)

        if removed:
            logger.info("Removed %d legacy JSON files", removed)

    # ------------------------------------------------------------------
    # Override: load from SQLite instead of JSON files
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load all records from SQLite into the in-memory pool."""
        if not self._db_path.exists():
            return

        conn = sqlite3.connect(str(self._db_path))
        try:
            cursor = conn.execute("SELECT * FROM records")
            columns = [desc[0] for desc in cursor.description]
            count = 0
            for row in cursor:
                data = dict(zip(columns, row))
                key = data.pop("id")
                data.pop("updated_at", None)
                # Map group_name → group for TASRecord.from_dict
                if "group_name" in data:
                    data["group"] = data.pop("group_name")
                self._pool[key] = TASRecord.from_dict(data)
                count += 1
            if count:
                logger.debug("Loaded %d records from SQLite", count)
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Override: defer writes to background flush
    # ------------------------------------------------------------------

    def _save_record(self, key: str, r: TASRecord) -> None:
        """Mark a record as dirty for deferred batched write to SQLite."""
        if self._closed:
            # If closed, write immediately
            self._flush_one(key, r)
            return
        with self._lock:
            self._sqlite_dirty[key] = r

    async def flush(self) -> None:
        """中文说明：flush。

Flush pending SQLite writes and sync echotools dirty state."""
        if self._flush_task is not None and not self._flush_task.done():
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        self._flush()

    def _flush_dirty_sync(self) -> None:
        """Sync echotools dirty keys into SQLite."""
        super()._flush_dirty_sync()
        self._flush_sqlite()

    # ------------------------------------------------------------------
    # Batched flush
    # ------------------------------------------------------------------

    def _flush(self) -> None:
        """Flush all dirty records to SQLite in a single batch."""
        self._flush_dirty_sync()

    def _flush_sqlite(self) -> None:
        """Write buffered SQLite dirty records in one transaction."""
        with self._lock:
            if not self._sqlite_dirty:
                return
            items = dict(self._sqlite_dirty)
            self._sqlite_dirty.clear()

        conn = sqlite3.connect(str(self._db_path))
        try:
            conn.executemany(
                """INSERT OR REPLACE INTO records
                   (id, group_name, n_success, n_fails, latency_sum, latency_sum_sq,
                    n_latency_samples, speed_sum, speed_sum_sq, n_speed_samples,
                    last_success, last_used, error_time, n_calls, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [(k, r.group, r.n_success, r.n_fails, r.latency_sum, r.latency_sum_sq,
                  r.n_latency_samples, r.speed_sum, r.speed_sum_sq, r.n_speed_samples,
                  r.last_success, r.last_used, r.error_time, r.n_calls, time.time())
                 for k, r in items.items()],
            )
            conn.commit()
        except Exception as e:
            logger.warning("Batch flush failed: %s", e)
        finally:
            conn.close()

    def _flush_one(self, key: str, r: TASRecord) -> None:
        """Flush a single record immediately (used when closed)."""
        conn = sqlite3.connect(str(self._db_path))
        try:
            conn.execute(
                """INSERT OR REPLACE INTO records
                   (id, group_name, n_success, n_fails, latency_sum, latency_sum_sq,
                    n_latency_samples, speed_sum, speed_sum_sq, n_speed_samples,
                    last_success, last_used, error_time, n_calls, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (key, r.group, r.n_success, r.n_fails, r.latency_sum, r.latency_sum_sq,
                 r.n_latency_samples, r.speed_sum, r.speed_sum_sq, r.n_speed_samples,
                 r.last_success, r.last_used, r.error_time, r.n_calls, time.time()),
            )
            conn.commit()
        except Exception as e:
            logger.warning("Flush record [%s] failed: %s", key, e)
        finally:
            conn.close()

    def _start_flush_thread(self) -> None:
        """Start a daemon thread that periodically flushes dirty records."""
        def loop() -> None:
            """公开方法 loop。"""
            while not self._closed:
                time.sleep(self._flush_interval)
                try:
                    self._flush()
                except Exception as e:
                    logger.warning("Periodic flush failed: %s", e)
            # Final flush on exit
            try:
                self._flush()
            except Exception:
                pass

        t = threading.Thread(target=loop, daemon=True, name="selector-flush")
        t.start()

    # ------------------------------------------------------------------
    # Override: prune stale records using SQL
    # ------------------------------------------------------------------

    def prune_stale(self) -> int:
        """中文说明：prune_stale。

Remove stale candidate records from SQLite and the in-memory pool.

Deletes records whose last_used time exceeds the configured threshold
and that have never successfully completed a call.

Returns:
    Number of candidate records pruned."""
        if not self._db_path.exists():
            return 0

        cutoff = time.time() - self._prune_days * 86400
        conn = sqlite3.connect(str(self._db_path))
        try:
            # Only prune records that have never succeeded
            cursor = conn.execute(
                "DELETE FROM records WHERE updated_at < ? AND n_calls = 0 AND n_fails > 0",
                (cutoff,),
            )
            pruned = cursor.rowcount
            conn.commit()

            # Sync in-memory pool
            for key in list(self._pool.keys()):
                r = self._pool[key]
                if r.last_used < cutoff and r.n_calls == 0:
                    self._pool.pop(key, None)

            if pruned:
                logger.info(
                    "pruned %d stale candidates from SQLite (older than %d days)",
                    pruned,
                    self._prune_days,
                )
            return pruned
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def close(self) -> None:
        """中文说明：close。

Flush all pending writes and close the selector."""
        self._closed = True
        self._flush()
