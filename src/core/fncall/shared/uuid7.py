# src/core/fncall/shared/uuid7.py
"""UUIDv7 生成。

从 src/core/tools.py 迁移（原 lines 82-109）。
"""

from __future__ import annotations

import secrets
import struct
import time
import uuid


def _uuid7() -> str:
    """生成时间有序的 UUIDv7 字符串。"""
    ts_ms = int(time.time() * 1000) & 0xFFFFFFFFFFFF

    rand_bytes = secrets.token_bytes(10)
    rand_a = struct.unpack(">H", rand_bytes[:2])[0] & 0x0FFF
    rand_b = struct.unpack(">Q", rand_bytes[2:])[0] & 0x3FFFFFFFFFFFFFFF

    uuid_int = (
        ts_ms << 80
        | 0x7 << 76
        | rand_a << 64
        | 0b10 << 62
        | rand_b
    )
    return str(uuid.UUID(int=uuid_int))
