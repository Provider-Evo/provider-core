"""跨进程通信（IPC）模块。"""
from __future__ import annotations

from src.core.server.infra.ipc.shared_memory import SharedMemoryManager

__all__ = ["SharedMemoryManager"]
