# -*- coding: utf-8 -*-
from __future__ import annotations

"""Virtual Key 存储与额度（参考 LiteLLM / One API Token 体系）。

异步版本使用 aiosqlite 减少事件循环阻塞。
"""

import hashlib
import secrets
import sqlite3
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import aiosqlite

from src.foundation.logger import get_logger
from src.foundation.paths import persist_db_dir

__all__ = [
    "AsyncVirtualKeyStore",
    "VirtualKeyStore",
    "get_virtual_key_store",
    "hash_key",
]

_log = get_logger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS virtual_keys (
    id TEXT PRIMARY KEY,
    key_hash TEXT NOT NULL UNIQUE,
    name TEXT DEFAULT '',
    quota_total INTEGER DEFAULT 0,
    quota_used INTEGER DEFAULT 0,
    expires_at REAL DEFAULT 0,
    models TEXT DEFAULT '',
    enabled INTEGER DEFAULT 1,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_vk_hash ON virtual_keys(key_hash);
"""


def hash_key(raw: str) -> str:
    """返回虚拟 Key 的 SHA-256 十六进制摘要。"""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class AsyncVirtualKeyStore:
    """异步 SQLite 持久化的 Virtual Key 存储。"""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = db_path or (persist_db_dir() / "virtual_keys.db")
        self._initialized = False

    @asynccontextmanager
    async def _conn(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """异步上下文管理器，提供数据库连接。"""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(str(self._db_path)) as conn:
            conn.row_factory = aiosqlite.Row
            if not self._initialized:
                await conn.executescript(_SCHEMA)
                self._initialized = True
            yield conn

    async def _ensure_schema(self) -> None:
        """确保数据库 schema 存在。"""
        if not self._initialized:
            async with self._conn():
                pass  # schema 在 _conn 中初始化

    async def create(
        self,
        *,
        name: str = "",
        quota_total: int = 0,
        expires_at: float = 0.0,
        models: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """创建新 Key 并返回含明文 `key` 字段的记录（仅此一次）。"""
        raw = "sk-vk-" + secrets.token_urlsafe(24)
        key_id = secrets.token_hex(8)
        models_csv = ",".join(models or [])
        now = time.time()
        async with self._conn() as conn:
            await conn.execute(
                """INSERT INTO virtual_keys
                   (id, key_hash, name, quota_total, quota_used, expires_at, models, enabled, created_at)
                   VALUES (?, ?, ?, ?, 0, ?, ?, 1, ?)""",
                (key_id, hash_key(raw), name, quota_total, expires_at, models_csv, now),
            )
            await conn.commit()
        return {
            "id": key_id,
            "key": raw,
            "name": name,
            "quota_total": quota_total,
            "quota_used": 0,
            "expires_at": expires_at,
            "models": models or [],
        }

    async def list_keys(self) -> List[Dict[str, Any]]:
        """列出所有 Key 的公开字段（不含哈希）。"""
        async with self._conn() as conn:
            cursor = await conn.execute(
                "SELECT id, name, quota_total, quota_used, expires_at, models, enabled, created_at "
                "FROM virtual_keys ORDER BY created_at DESC"
            )
            rows = await cursor.fetchall()
        return [self._row_public(r) for r in rows]

    async def delete(self, key_id: str) -> bool:
        """按 id 删除 Key，存在则返回 True。"""
        async with self._conn() as conn:
            cursor = await conn.execute(
                "DELETE FROM virtual_keys WHERE id = ?", (key_id,)
            )
            await conn.commit()
            return cursor.rowcount > 0

    async def authenticate(self, raw_key: str) -> Optional[Dict[str, Any]]:
        """校验明文 Key；过期、禁用或超额时返回 None。"""
        if not raw_key:
            return None
        async with self._conn() as conn:
            cursor = await conn.execute(
                "SELECT * FROM virtual_keys WHERE key_hash = ? AND enabled = 1",
                (hash_key(raw_key),),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        if row["expires_at"] and row["expires_at"] < time.time():
            return None
        quota_total = int(row["quota_total"] or 0)
        quota_used = int(row["quota_used"] or 0)
        if quota_total > 0 and quota_used >= quota_total:
            return None
        models = [m for m in str(row["models"] or "").split(",") if m]
        return {
            "id": row["id"],
            "name": row["name"],
            "quota_total": quota_total,
            "quota_used": quota_used,
            "models": models,
        }

    async def consume(self, key_id: str, units: int = 1) -> None:
        """递增 Key 已用额度；units <= 0 时无操作。"""
        if units <= 0:
            return
        async with self._conn() as conn:
            await conn.execute(
                "UPDATE virtual_keys SET quota_used = quota_used + ? WHERE id = ?",
                (units, key_id),
            )
            await conn.commit()

    @staticmethod
    def _row_public(row: aiosqlite.Row) -> Dict[str, Any]:
        models = [m for m in str(row["models"] or "").split(",") if m]
        return {
            "id": row["id"],
            "name": row["name"],
            "quota_total": int(row["quota_total"] or 0),
            "quota_used": int(row["quota_used"] or 0),
            "expires_at": float(row["expires_at"] or 0),
            "models": models,
            "enabled": bool(row["enabled"]),
            "created_at": float(row["created_at"] or 0),
        }


# ------------------------------------------------------------------
# 同步包装器：中间件等同步调用点无法 await AsyncVirtualKeyStore
# ------------------------------------------------------------------


class VirtualKeyStore:
    """同步包装器，内部委托给 AsyncVirtualKeyStore。

    用于不支持异步的调用点（如中间件同步路径）。
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._async_store = AsyncVirtualKeyStore(db_path)
        self._init_lock = __import__("threading").Lock()
        self._ensure_sync()

    def _ensure_sync(self) -> None:
        """同步确保 schema 存在。"""
        if self._async_store._initialized:
            return
        with self._init_lock:
            if self._async_store._initialized:
                return
            self._async_store._initialized = True
            # 同步创建数据库和 schema
            db_path = self._async_store._db_path
            db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(db_path))
            try:
                conn.executescript(_SCHEMA)
            finally:
                conn.close()

    def create(
        self,
        *,
        name: str = "",
        quota_total: int = 0,
        expires_at: float = 0.0,
        models: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """同步创建新 Key。"""
        self._ensure_sync()
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            # 在异步上下文中，使用线程池执行
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(
                    asyncio.run,
                    self._async_store.create(
                        name=name,
                        quota_total=quota_total,
                        expires_at=expires_at,
                        models=models,
                    ),
                ).result()
        else:
            return asyncio.run(
                self._async_store.create(
                    name=name,
                    quota_total=quota_total,
                    expires_at=expires_at,
                    models=models,
                )
            )

    def list_keys(self) -> List[Dict[str, Any]]:
        """同步列出所有 Key。"""
        self._ensure_sync()
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, self._async_store.list_keys()).result()
        else:
            return asyncio.run(self._async_store.list_keys())

    def delete(self, key_id: str) -> bool:
        """同步删除 Key。"""
        self._ensure_sync()
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(
                    asyncio.run, self._async_store.delete(key_id)
                ).result()
        else:
            return asyncio.run(self._async_store.delete(key_id))

    def authenticate(self, raw_key: str) -> Optional[Dict[str, Any]]:
        """同步校验 Key。"""
        self._ensure_sync()
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(
                    asyncio.run, self._async_store.authenticate(raw_key)
                ).result()
        else:
            return asyncio.run(self._async_store.authenticate(raw_key))

    def consume(self, key_id: str, units: int = 1) -> None:
        """同步消费额度。"""
        self._ensure_sync()
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                pool.submit(
                    asyncio.run, self._async_store.consume(key_id, units)
                ).result()
        else:
            asyncio.run(self._async_store.consume(key_id, units))


_store: Optional[AsyncVirtualKeyStore] = None


def get_virtual_key_store() -> AsyncVirtualKeyStore:
    """返回进程级单例 AsyncVirtualKeyStore。"""
    global _store
    if _store is None:
        _store = AsyncVirtualKeyStore()
    return _store


# 旧脚本/测试仍 import get_sync_virtual_key_store；勿删，否则同步路径会各自打开第二份 DB
def get_sync_virtual_key_store() -> VirtualKeyStore:
    """返回同步版本的 VirtualKeyStore（用于向后兼容）。"""
    return VirtualKeyStore(_store._db_path if _store else None)
