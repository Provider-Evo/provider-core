from __future__ import annotations

"""终端实时输出桥接 — 子类化 echotools 会话，避免 monkey-patch。"""

import asyncio

from echotools.terminal import LocalTerminal, SSHTerminal
from echotools.terminal.session import MAX_OFFLINE_BUFFER_BYTES, TerminalSession

__all__ = ["BridgedLocalTerminal", "BridgedSSHTerminal"]


class _LiveOutputSessionMixin:
    """在 history 追加之前投递实时输出，避免 ConPTY 读循环阻塞。"""

    async def _fire_output(self, data: str) -> None:
        if self._callbacks:
            for cb in list(self._callbacks):
                if cb.on_output is not None:
                    try:
                        await cb.on_output(data)
                    except Exception:
                        pass
        else:
            self._offline_buffer += data
            self._offline_buffer_size += len(data)
            if self._offline_buffer_size > MAX_OFFLINE_BUFFER_BYTES:
                excess = self._offline_buffer_size - MAX_OFFLINE_BUFFER_BYTES
                self._offline_buffer = self._offline_buffer[excess:]
                self._offline_buffer_size = len(self._offline_buffer)

        lock = self.__dict__.setdefault("_history_append_lock", asyncio.Lock())

        async def _append_history_bg() -> None:
            async with lock:
                await asyncio.to_thread(self._append_history, data)

        asyncio.create_task(_append_history_bg())


class BridgedLocalTerminal(_LiveOutputSessionMixin, LocalTerminal):
    """本地终端：优先广播实时输出。"""


class BridgedSSHTerminal(_LiveOutputSessionMixin, SSHTerminal):
    """SSH 终端：优先广播实时输出。"""
