"""Selector migration helpers — standalone functions used by Selector.__init__."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict

from echotools.dispatch.selector import TASRecord

from src.foundation.logger import get_logger

logger = get_logger(__name__)

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


def convert_legacy_data(data: dict) -> TASRecord | None:
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


def _db_has_records(db_path: Path) -> bool:
    """Return True if the SQLite database already contains records."""
    conn = sqlite3.connect(str(db_path))
    try:
        count = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
        return count > 0
    finally:
        conn.close()


def _migrate_one_json_file(conn: sqlite3.Connection, f: Path) -> bool:
    """Migrate a single legacy JSON file into the records table.

    Returns True if a record was inserted.
    """
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        key = f.stem

        # Handle both old EMA format and new summary format
        record = convert_legacy_data(data)
        if record is None:
            return False

        conn.execute(
            """INSERT OR REPLACE INTO records
               (id, group_name, n_success, n_fails, latency_sum,
                latency_sum_sq, n_latency_samples, speed_sum,
                speed_sum_sq, n_speed_samples, last_success,
                last_used, error_time, n_calls, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                key,
                record.group,
                record.n_success,
                record.n_fails,
                record.latency_sum,
                record.latency_sum_sq,
                record.n_latency_samples,
                record.speed_sum,
                record.speed_sum_sq,
                record.n_speed_samples,
                record.last_success,
                record.last_used,
                record.error_time,
                record.n_calls,
                time.time(),
            ),
        )
        return True
    except Exception as e:
        logger.debug("Failed to migrate %s: %s", f.name, e)
        return False


def _migrate_json_files_to_db(db_path: Path, json_files: list) -> int:
    """Migrate all given legacy JSON files into the SQLite database.

    Returns the number of records migrated.
    """
    migrated = 0
    conn = sqlite3.connect(str(db_path))
    try:
        for f in json_files:
            if f.name.startswith("_"):
                continue
            if _migrate_one_json_file(conn, f):
                migrated += 1
        conn.commit()
    finally:
        conn.close()
    return migrated


def migrate_json_if_needed(db_path: Path, pool: Dict[str, Any]) -> None:
    """Migrate legacy JSON files to SQLite if the database is empty.

    Args:
        db_path: Path to the SQLite database file.
        pool: In-memory record pool (not populated here; used only for
              the early-return check when db already has records).
    """
    if not db_path.exists():
        return

    if _db_has_records(db_path):
        return

    # No records in db — try to migrate from JSON files
    json_files = list(db_path.parent.glob("*.json"))
    if not json_files:
        return

    logger.info("Migrating %d legacy JSON files to SQLite", len(json_files))
    migrated = _migrate_json_files_to_db(db_path, json_files)

    if migrated:
        logger.info("Successfully migrated %d records to SQLite", migrated)

    # Clean up legacy JSON files
    cleanup_json_files(db_path.parent)


def cleanup_json_files(persist_dir: Path) -> None:
    """Remove legacy JSON files after migration.

    Args:
        persist_dir: Directory containing the JSON files.
    """
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
