from __future__ import annotations

"""TerminalSession 生命周期 mixin — 启动/重启/关闭底层终端进程。"""

import asyncio
import sys
from typing import Any, Dict, List, Optional

from echotools.terminal import TerminalCallback

from src.foundation.config import get_config
from src.core.server.terminal.session_audit import get_audit_store
from src.webui.routers.session.terminal.out_bridge import (
    BridgedLocalTerminal,
    BridgedSSHTerminal,
    BridgedTmuxTerminal,
)
from src.webui.routers.session.terminal.term_proto import wrap_atomic_replay

try:
    from echotools.terminal.tmux import tmux_available
except ImportError:
    import shutil

    def tmux_available() -> bool:
        if sys.platform == "win32":
            return False
        return shutil.which("tmux") is not None


class _LifecycleMixin:
    """负责底层终端进程的启动、重启与关闭。"""

    def _local_terminal_class(self) -> type:
        cfg = get_config().terminal
        if (
            cfg.backend.strip().lower() == "tmux"
            and sys.platform != "win32"
            and tmux_available()
        ):
            return BridgedTmuxTerminal
        return BridgedLocalTerminal

    async def start_local(self, cols: int = 80, rows: int = 24) -> bool:
        """创建并启动本地终端会话。"""
        terminal_cls = self._local_terminal_class()
        self._terminal = terminal_cls(self.session_id)
        ok = await self._terminal.start(cols, rows)
        if ok:
            self.alive = True
            self.readonly = False
            self._ensure_writer()
            if self._store:
                self._store.save(
                    session_id=self.session_id,
                    pid=self._terminal.pid,
                    cols=cols,
                    rows=rows,
                    kind="local",
                    name=self.name,
                    status="alive",
                    backend=get_config().terminal.backend,
                )
            if get_config().terminal.audit_enabled:
                get_audit_store().record_start(self.session_id, "本地", "local")
        return ok

    async def start_ssh(
        self,
        host: str,
        port: int = 22,
        username: str = "",
        password: str = "",
        key_data: str = "",
        cols: int = 80,
        rows: int = 24,
        connection_id: Optional[str] = None,
        trust_host_key: bool = True,
    ) -> bool:
        """创建并启动 SSH 远程终端会话。"""
        self.last_start_error = None
        self._connection_id = connection_id
        self._ssh_config = {
            "host": host,
            "port": port,
            "username": username,
            "password": password,
            "key_data": key_data,
            "connection_id": connection_id,
            "trust_host_key": trust_host_key,
        }
        ok = await self._start_ssh_terminal(
            host, port, username, password, key_data, cols, rows, trust_host_key
        )
        if not ok:
            return False

        self.alive = True
        self.readonly = False
        self._ensure_writer()
        self._persist_ssh_start(host, port, username, cols, rows, connection_id)
        return True

    async def _start_ssh_terminal(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        key_data: str,
        cols: int,
        rows: int,
        trust_host_key: bool,
    ) -> bool:
        captured_errors: List[str] = []

        async def _capture_start_error(message: str) -> None:
            captured_errors.append(message)

        self._terminal = BridgedSSHTerminal(
            self.session_id,
            host=host,
            port=port,
            username=username,
            password=password or None,
            key_data=(key_data or "").strip() or None,
        )
        self._terminal._trust_host_key = trust_host_key
        self._terminal.attach(TerminalCallback(on_error=_capture_start_error))
        ok = await self._terminal.start(cols, rows)
        if not ok:
            self.last_start_error = (
                captured_errors[-1] if captured_errors else "SSH connection failed"
            )
            self.alive = False
        return ok

    def _persist_ssh_start(
        self, host: str, port: int, username: str, cols: int, rows: int, connection_id: Optional[str]
    ) -> None:
        if self._store:
            self._store.save(
                session_id=self.session_id,
                pid=None,
                cols=cols,
                rows=rows,
                kind="ssh",
                ssh_config={
                    "host": host,
                    "port": port,
                    "username": username,
                    "connection_id": connection_id,
                },
                name=self.name,
                status="alive",
            )
        if get_config().terminal.audit_enabled:
            get_audit_store().record_start(self.session_id, host, "ssh")

    def _ensure_writer(self) -> None:
        if self._writer_task is None or self._writer_task.done():
            self._writer_task = asyncio.create_task(self._output_writer_loop())

    async def _shutdown_terminal(self) -> None:
        if self._terminal is None:
            return
        kill = self._terminal.kill if hasattr(self._terminal, "kill") else None
        if callable(kill):
            await kill()
        else:
            await self._terminal.close()
        self._terminal = None
        if self._writer_task and not self._writer_task.done():
            self._writer_task.cancel()
            try:
                await self._writer_task
            except asyncio.CancelledError:
                pass
        self._writer_task = None

    async def restart(self, cols: int = 80, rows: int = 24) -> bool:
        if self.kind == "ssh":
            if not self._ssh_config:
                self.last_start_error = "SSH session settings are unavailable for restart"
                return False
            await self._shutdown_terminal()
            cfg = self._ssh_config
            return await self.start_ssh(
                host=str(cfg.get("host", "")),
                port=int(cfg.get("port", 22)),
                username=str(cfg.get("username", "")),
                password=str(cfg.get("password", "")),
                key_data=str(cfg.get("key_data", "")),
                cols=cols,
                rows=rows,
                connection_id=cfg.get("connection_id"),
                trust_host_key=bool(cfg.get("trust_host_key", True)),
            )

        if not self._terminal:
            return False
        await self._shutdown_terminal()
        terminal_cls = self._local_terminal_class()
        self._terminal = terminal_cls(self.session_id)
        if not await self._terminal.start(cols, rows):
            return False
        await self._reattach_clients_after_restart()
        return True

    async def _reattach_clients_after_restart(self) -> None:
        self._client_callbacks.clear()
        for ws in list(self._clients):
            callback = TerminalCallback(
                on_output=self._broadcast_output,
                on_error=self._broadcast_error,
                on_exit=self._broadcast_exit,
                on_metadata=self._broadcast_metadata,
            )
            self._client_callbacks[ws] = callback
            if self._terminal:
                self._terminal.attach(callback)
        if self._terminal:
            snapshot = wrap_atomic_replay(self._terminal.history)
            asyncio.create_task(
                self._output_queue.put(
                    (self._terminal.output_seq, snapshot.encode("utf-8", errors="replace"))
                )
            )

    async def write(self, data: str) -> None:
        if self._terminal and not self.readonly:
            await self._terminal.write(data)

    async def write_bytes(self, data: bytes) -> None:
        text = data.decode("utf-8", errors="replace")
        await self.write(text)

    async def resize(self, cols: int, rows: int) -> None:
        if self._terminal:
            await self._terminal.resize(cols, rows)

    async def kill(self) -> None:
        self.alive = False
        if self._terminal:
            await self._shutdown_terminal()
        self._client_callbacks.clear()
        self._client_writable.clear()
        self._primary_client = None

        if self._store:
            self._store.save(
                session_id=self.session_id,
                status="destroyed",
                kind=self.kind,
            )
        if get_config().terminal.audit_enabled:
            get_audit_store().record_status(self.session_id, "destroyed")

        for ws in list(self._clients):
            try:
                if not ws.closed:
                    await ws.send_json({
                        "type": "session_closed",
                        "session_id": self.session_id,
                    })
            except (ConnectionError, RuntimeError):
                self._logger.debug("Failed to notify client of session close", exc_info=True)
        self._clients.clear()
        from src.webui.routers.session.terminal.session_all.reg import sessions_registry

        sessions_registry().pop(self.session_id, None)

    async def close(self) -> None:
        await self.kill()

    async def detach_for_shutdown(self) -> None:
        """Graceful shutdown: flush state, detach clients, keep shell if configured."""
        for ws in list(self._clients):
            self.detach_client(ws)
        if self._terminal and self._store:
            self._terminal.save_state(self._store.persist_dir)
            self._store.save_output_seq(
                self.session_id,
                self._terminal.output_seq,
            )
