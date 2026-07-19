from __future__ import annotations

"""TerminalSession 输出广播 mixin — 输出队列写循环与客户端广播。"""

import asyncio
from typing import Any, Dict, List

import aiohttp.web

from src.core.server.terminal.session_audit import get_audit_store
from src.foundation.config import get_config
from src.webui.routers.session.terminal.term_proto import encode_output_frame


class _BroadcastMixin:
    """负责将底层终端输出投递到已连接的 WebSocket 客户端。"""

    async def _output_writer_loop(self) -> None:
        """解耦 PTY 读循环与 WebSocket 写（T1.2）。"""
        try:
            while self._clients or self.alive:
                try:
                    seq, payload = await asyncio.wait_for(
                        self._output_queue.get(), timeout=0.5
                    )
                except asyncio.TimeoutError:
                    continue
                await self._flush_output_frame(seq, payload)
        except asyncio.CancelledError:
            pass

    async def _flush_output_frame(self, seq: int, payload: bytes) -> None:
        frame = encode_output_frame(seq, payload)
        dead: List[aiohttp.web.WebSocketResponse] = []
        for ws in list(self._clients):
            if ws in self._paused_clients:
                continue
            try:
                if not ws.closed:
                    await ws.send_bytes(frame)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._drop_client(ws)

    async def _broadcast_output(self, data: str) -> None:
        if not data or self._terminal is None:
            return
        seq = self._terminal.output_seq
        encoded = data.encode("utf-8", errors="replace")
        await self._output_queue.put((seq, encoded))

        if self._store:
            _loop = asyncio.get_running_loop()
            asyncio.create_task(
                _loop.run_in_executor(
                    None, self._store.append_output, self.session_id, data
                )
            )
            asyncio.create_task(
                _loop.run_in_executor(
                    None, self._store.save_output_seq, self.session_id, seq
                )
            )

    async def _broadcast_error(self, message: str) -> None:
        dead_clients = []
        for ws in list(self._clients):
            try:
                if not ws.closed:
                    await ws.send_json({"type": "error", "message": message})
            except Exception:
                dead_clients.append(ws)
        for ws in dead_clients:
            self._drop_client(ws)

    async def _broadcast_exit(self, code: int) -> None:
        self.alive = False
        if self._store:
            self._store.save(
                session_id=self.session_id,
                status="exited",
                kind=self.kind,
            )
        if get_config().terminal.audit_enabled:
            get_audit_store().record_status(self.session_id, "exited")
        dead_clients = []
        for ws in list(self._clients):
            try:
                if not ws.closed:
                    await ws.send_json({"type": "exit", "code": code})
            except Exception:
                dead_clients.append(ws)
        for ws in dead_clients:
            self._drop_client(ws)

    async def _broadcast_metadata(self, metadata: Dict[str, Any]) -> None:
        dead_clients = []
        for ws in list(self._clients):
            try:
                if not ws.closed:
                    await ws.send_json({"type": "metadata", **metadata})
            except Exception:
                dead_clients.append(ws)
        for ws in dead_clients:
            self._drop_client(ws)
