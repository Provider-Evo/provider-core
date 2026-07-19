"""terminal_protocol 模块 — WebUI 层。

职责：
    作为 Provider-Evo 项目标准模块，提供 terminal_protocol 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""

import struct
from typing import Optional, Tuple

__all__ = [
    "PROTOCOL_VERSION",
    "BSU",
    "ESU",
    "encode_output_frame",
    "decode_output_frame",
    "wrap_atomic_replay",
    "unwrap_atomic_replay",
]

PROTOCOL_VERSION = 2

# DEC 2026 synchronized output (gmux-style atomic scrollback replay).
BSU = "\x1b[?2026h"
ESU = "\x1b[?2026l"

_FRAME_HEADER = struct.Struct(">IB")


def encode_output_frame(seq: int, data: bytes) -> bytes:
    """Pack ``[u32 seq][u8 flags=0][payload]`` as a single binary WS frame."""
    if seq < 0:
        seq = 0
    header = _FRAME_HEADER.pack(seq & 0xFFFFFFFF, 0)
    return header + data


def decode_output_frame(payload: bytes) -> Tuple[int, bytes]:
    """Decode binary output frame; returns ``(seq, data)``."""
    if len(payload) < _FRAME_HEADER.size:
        return 0, payload
    seq, _flags = _FRAME_HEADER.unpack_from(payload)
    return int(seq), payload[_FRAME_HEADER.size :]


def wrap_atomic_replay(data: str) -> str:
    """Wrap replay scrollback for flicker-free xterm redraw."""
    if not data:
        return ""
    if data.startswith(BSU):
        return data
    return f"{BSU}\x1b[2J\x1b[H{data}{ESU}"


def unwrap_atomic_replay(data: str) -> Optional[str]:
    """Return inner replay if *data* is a complete BSU..ESU block."""
    if not data.startswith(BSU):
        return None
    end = data.rfind(ESU)
    if end < 0:
        return None
    inner = data[len(BSU) : end]
    if inner.startswith("\x1b[2J\x1b[H"):
        inner = inner[6:]
    return inner
