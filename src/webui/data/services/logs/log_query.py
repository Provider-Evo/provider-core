from __future__ import annotations

"""WebUI 请求日志——异步查询层。

提供 load_requests、get_request_count、query_requests 三个异步接口。
"""

import json
from typing import Any

import aiosqlite
from echotools.web.broker import request_broker

from src.webui.data.services.logs.log_store import (
    _DB_PATH,
    _MAX_BUFFER,
    MAX_QUERY_LIMIT,
    _log,
    clamp_query_limit,
)


async def load_requests() -> None:
    """从 SQLite 加载最近 N 条到内存 buffer（异步，避免阻塞事件循环）。"""
    if not _DB_PATH.exists():
        return
    try:
        async with aiosqlite.connect(str(_DB_PATH)) as conn:
            cursor = await conn.execute(
                "SELECT * FROM request_logs ORDER BY ts DESC LIMIT ?",
                (_MAX_BUFFER,),
            )
            columns = [desc[0] for desc in cursor.description]
            count = 0
            async for row in cursor:
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
    except Exception:
        _log.debug("Failed to restore request logs", exc_info=True)


async def get_request_count() -> int:
    """返回数据库中的总记录数（异步）。"""
    if not _DB_PATH.exists():
        return 0
    try:
        async with aiosqlite.connect(str(_DB_PATH)) as conn:
            cursor = await conn.execute("SELECT COUNT(*) FROM request_logs")
            row = await cursor.fetchone()
            return row[0]
    except Exception:
        return 0


async def query_requests(
    limit: int = 50,
    model: str = "",
    platform: str = "",
    status: int | None = None,
    since: float = 0.0,
) -> list[dict]:
    """从 SQLite 查询请求日志，支持筛选（异步）。"""
    limit = clamp_query_limit(limit)
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
    sql = "SELECT * FROM request_logs WHERE {} ORDER BY ts DESC LIMIT ?".format(where)
    params.append(limit)

    async with aiosqlite.connect(str(_DB_PATH)) as conn:
        cursor = await conn.execute(sql, params)
        columns = [desc[0] for desc in cursor.description]
        rows = await cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]
