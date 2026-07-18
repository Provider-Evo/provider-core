from __future__ import annotations

"""TerminalSession 客户端挂接 mixin — attach/detach/背压/主客户端选取。"""

import asyncio
from typing import Any, Dict

import aiohttp.web
from echotools.terminal import TerminalCallback

from src.webui.routers.session.terminal.term_proto import (
    PROTOCOL_VERSION,
    wrap_atomic_replay,
)


class _ClientsMixin:
    """负责 WebSocket 客户端的挂接、断开与写权限管理。"""

    def _pick_primary_client(self) -> None:
        self._primary_client = None
        for ws in self._clients:
            if self._client_writable.get(ws, False):
                self._primary_client = ws
                break

    def can_client_write(self, ws: aiohttp.web.WebSocketResponse) -> bool:
        if self.readonly or not self.alive:
            return False
        return self._primary_client is ws and self._client_writable.get(ws, False)

    def _init_attach(self, ws: aiohttp.web.WebSocketResponse, writable: bool) -> None:
        self._clients.add(ws)
        is_writable = writable and not self.readonly and self.alive
        if is_writable and self._primary_client is None:
            self._client_writable[ws] = True
            self._primary_client = ws
        else:
            self._client_writable[ws] = False

    def _attach_offline_replay(self, ws: aiohttp.web.WebSocketResponse, since_seq: int) -> Any:
        replay_data = ""
        head_seq = 0
        if self._store:
            replay_data = self._store.consume_offline_output(self.session_id)
            head_seq = self._store.get_output_seq(self.session_id)
        self._client_writable[ws] = False
        return since_seq, replay_data, head_seq

    def _attach_live_replay(self, ws: aiohttp.web.WebSocketResponse, since_seq: int) -> Any:
        replay_from = since_seq
        replay_data = ""
        callback = TerminalCallback(
            on_output=self._broadcast_output,
            on_error=self._broadcast_error,
            on_exit=self._broadcast_exit,
            on_metadata=self._broadcast_metadata,
        )
        self._client_callbacks[ws] = callback
        buffered = self._terminal.attach(callback)
        head_seq = self._terminal.output_seq
        effective, ring_replay = self._terminal.replay_from(since_seq)
        if ring_replay:
            replay_from = effective
            replay_data = ring_replay
        elif buffered:
            replay_data = buffered
            replay_from = max(0, head_seq - 1)

        if self._store and replay_data:
            self._store.append_output(self.session_id, replay_data)
        elif self._store:
            persisted = self._store.get_offline_output(self.session_id)
            if persisted and since_seq <= 0:
                replay_data = persisted
                self._store.clear_offline_output(self.session_id)
        return replay_from, replay_data, head_seq

    def attach_client(
        self,
        ws: aiohttp.web.WebSocketResponse,
        *,
        since_seq: int = 0,
        writable: bool = True,
    ) -> Dict[str, Any]:
        """挂接 WebSocket；返回 attach 元数据供 ``attached`` 控制消息。"""
        self._init_attach(ws, writable)

        if not self.reattachable:
            replay_from, replay_data, head_seq = self._attach_offline_replay(ws, since_seq)
        elif self._terminal is not None:
            replay_from, replay_data, head_seq = self._attach_live_replay(ws, since_seq)
        else:
            replay_from, replay_data, head_seq = since_seq, "", 0

        if replay_data and since_seq <= 0:
            replay_data = wrap_atomic_replay(replay_data)

        self._ensure_writer()
        if replay_data:
            encoded = replay_data.encode("utf-8", errors="replace")
            seq_for_replay = max(replay_from, 1)
            asyncio.create_task(
                self._output_queue.put((seq_for_replay, encoded))
            )

        mode = "live" if self.can_client_write(ws) else "readonly"
        return {
            "mode": mode,
            "replay_from_seq": replay_from,
            "head_seq": head_seq or (self._terminal.output_seq if self._terminal else 0),
            "writable": self.can_client_write(ws),
            "protocol_version": PROTOCOL_VERSION,
        }

    def detach_client(self, ws: aiohttp.web.WebSocketResponse) -> None:
        self._clients.discard(ws)
        self._paused_clients.discard(ws)
        callback = self._client_callbacks.pop(ws, None)
        self._client_writable.pop(ws, None)
        if self._primary_client is ws:
            self._primary_client = None
            self._pick_primary_client()

        if self._terminal is not None and callback is not None:
            self._terminal.detach_callback(callback)

        if not self._clients and self._terminal is not None:
            self._terminal.detach()
            self._logger.info(
                "Session %s: all clients detached, process kept alive",
                self.session_id,
            )

    def _drop_client(self, ws: aiohttp.web.WebSocketResponse) -> None:
        self.detach_client(ws)

    async def set_client_backpressure(
        self,
        ws: aiohttp.web.WebSocketResponse,
        paused: bool,
    ) -> None:
        if paused:
            self._paused_clients.add(ws)
        else:
            self._paused_clients.discard(ws)
        if self._terminal is None:
            return
        if any(c not in self._paused_clients for c in self._clients):
            self._terminal.resume_output()
        else:
            self._terminal.pause_output()

    async def clear(self) -> None:
        if self._terminal:
            await self._terminal.clear_history()
        for ws in list(self._clients):
            try:
                if not ws.closed:
                    await ws.send_json({"type": "history_cleared"})
            except Exception:
                self._drop_client(ws)
