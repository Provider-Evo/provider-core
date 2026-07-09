from __future__ import annotations

"""WebUI 终端会话状态机 — 进程生命周期与多客户端广播。"""

import asyncio
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import aiohttp.web
from echotools.terminal import TerminalCallback

from src.core.server.terminal.sessions import TerminalSessionStore
from src.foundation.logger import get_logger
from src.webui.routers.session.terminal.terminal_output_bridge import BridgedLocalTerminal, BridgedSSHTerminal

logger = get_logger(__name__)

__all__ = [
    "TerminalSession",
    "get_session",
    "list_sessions",
    "recover_sessions",
    "sessions_registry",
]


class TerminalSession:
    """服务端终端会话：管理底层进程与已连接的 WebSocket 客户端。"""

    def __init__(self, session_id: str, kind: str) -> None:
        self.session_id = session_id
        self.kind = kind
        self._terminal: Optional[BridgedLocalTerminal | BridgedSSHTerminal] = None
        self._clients: Set[aiohttp.web.WebSocketResponse] = set()
        self._client_callbacks: Dict[aiohttp.web.WebSocketResponse, TerminalCallback] = {}
        self._store: Optional[TerminalSessionStore] = None
        self.alive: bool = False
        self.name: Optional[str] = None
        self.reattachable: bool = True
        self._ssh_config: Optional[Dict[str, Any]] = None
        self.last_start_error: Optional[str] = None

    async def start_local(self, cols: int = 80, rows: int = 24) -> bool:
        """创建并启动本地终端会话。"""
        self._terminal = BridgedLocalTerminal(self.session_id)
        ok = await self._terminal.start(cols, rows)
        if ok:
            self.alive = True
            if self._store:
                self._store.save(
                    session_id=self.session_id,
                    pid=self._terminal.pid,
                    cols=cols,
                    rows=rows,
                    kind="local",
                    name=self.name,
                    status="alive",
                )
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
    ) -> bool:
        """创建并启动 SSH 远程终端会话。"""
        self.last_start_error = None
        self._ssh_config = {
            "host": host,
            "port": port,
            "username": username,
            "password": password,
            "key_data": key_data,
        }
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
        self._terminal.attach(TerminalCallback(on_error=_capture_start_error))
        ok = await self._terminal.start(cols, rows)
        if not ok:
            self.last_start_error = (
                captured_errors[-1]
                if captured_errors
                else "SSH connection failed"
            )
            self.alive = False
            return False

        self.alive = True
        if self._store:
            self._store.save(
                session_id=self.session_id,
                pid=None,
                cols=cols,
                rows=rows,
                kind="ssh",
                ssh_config={"host": host, "port": port, "username": username},
                name=self.name,
                status="alive",
            )
        return True

    async def _shutdown_terminal(self) -> None:
        """停止底层终端进程。"""
        if self._terminal is None:
            return
        kill = getattr(self._terminal, "kill", None)
        if callable(kill):
            await kill()
        else:
            await self._terminal.close()
        self._terminal = None

    def attach_client(self, ws: aiohttp.web.WebSocketResponse) -> Optional[str]:
        """将 WebSocket 客户端挂接到本会话，返回待刷新的离线输出。"""
        self._clients.add(ws)

        if not self.reattachable:
            if self._store:
                offline = self._store.consume_offline_output(self.session_id)
                return offline if offline else None
            return None

        if self._terminal is not None:
            callback = TerminalCallback(
                on_output=self._broadcast_output,
                on_error=self._broadcast_error,
                on_exit=self._broadcast_exit,
                on_metadata=self._broadcast_metadata,
            )
            self._client_callbacks[ws] = callback
            buffered = self._terminal.attach(callback)

            if self._store and buffered:
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(
                        asyncio.to_thread(
                            self._store.append_output, self.session_id, buffered
                        )
                    )
                except RuntimeError:
                    self._store.append_output(self.session_id, buffered)
            elif self._store:
                persisted = self._store.get_offline_output(self.session_id)
                if persisted:
                    buffered = persisted
                    self._store.clear_offline_output(self.session_id)

            return buffered if buffered else None
        return None

    def detach_client(self, ws: aiohttp.web.WebSocketResponse) -> None:
        """解除 WebSocket 挂接；无客户端时进程仍保持运行。"""
        self._clients.discard(ws)
        callback = self._client_callbacks.pop(ws, None)

        if self._terminal is not None and callback is not None:
            self._terminal.detach_callback(callback)

        if not self._clients and self._terminal is not None:
            self._terminal.detach()
            logger.info(
                "Session %s: all clients detached, process kept alive",
                self.session_id,
            )

    async def _broadcast_output(self, data: str) -> None:
        """向所有已连接客户端广播终端输出。"""
        dead_clients = []
        for ws in list(self._clients):
            try:
                if not ws.closed:
                    await ws.send_json({"type": "output", "data": data})
            except Exception:
                dead_clients.append(ws)

        for ws in dead_clients:
            self._clients.discard(ws)

        if self._store:
            asyncio.create_task(
                asyncio.to_thread(
                    self._store.append_output, self.session_id, data
                )
            )

    async def _broadcast_error(self, message: str) -> None:
        """向所有已连接客户端广播错误消息。"""
        dead_clients = []
        for ws in list(self._clients):
            try:
                if not ws.closed:
                    await ws.send_json({"type": "error", "message": message})
            except Exception:
                dead_clients.append(ws)
        for ws in dead_clients:
            self._clients.discard(ws)

    async def _broadcast_exit(self, code: int) -> None:
        """向所有已连接客户端广播进程退出事件。"""
        self.alive = False

        if self._store:
            self._store.save(
                session_id=self.session_id,
                status="exited",
                kind=self.kind,
            )

        dead_clients = []
        for ws in list(self._clients):
            try:
                if not ws.closed:
                    await ws.send_json({"type": "exit", "code": code})
            except Exception:
                dead_clients.append(ws)
        for ws in dead_clients:
            self._clients.discard(ws)

    async def _broadcast_metadata(self, metadata: Dict[str, Any]) -> None:
        """向所有已连接客户端广播元数据。"""
        dead_clients = []
        for ws in list(self._clients):
            try:
                if not ws.closed:
                    await ws.send_json({"type": "metadata", **metadata})
            except Exception:
                dead_clients.append(ws)
        for ws in dead_clients:
            self._clients.discard(ws)

    async def clear(self) -> None:
        """清空终端历史并通知所有客户端。"""
        if self._terminal:
            await self._terminal.clear_history()

        dead_clients = []
        for ws in list(self._clients):
            try:
                if not ws.closed:
                    await ws.send_json({"type": "history_cleared"})
            except Exception:
                dead_clients.append(ws)
        for ws in dead_clients:
            self._clients.discard(ws)

    async def _broadcast_snapshot(self, snapshot: str) -> None:
        """向所有客户端推送终端快照。"""
        dead_clients = []
        for ws in list(self._clients):
            try:
                if not ws.closed:
                    await ws.send_json({"type": "snapshot", "history": snapshot})
            except Exception:
                dead_clients.append(ws)
        for ws in dead_clients:
            self._clients.discard(ws)

    async def _reattach_clients_after_restart(self) -> None:
        """重启后重新挂接所有 WebSocket 客户端回调。"""
        self._client_callbacks.clear()
        for ws in list(self._clients):
            callback = TerminalCallback(
                on_output=self._broadcast_output,
                on_error=self._broadcast_error,
                on_exit=self._broadcast_exit,
                on_metadata=self._broadcast_metadata,
            )
            self._client_callbacks[ws] = callback
            self._terminal.attach(callback)
        await self._broadcast_snapshot(self._terminal.history)

    async def restart(self, cols: int = 80, rows: int = 24) -> bool:
        """重启终端会话（保持同一标签页）。"""
        if self.kind == "ssh":
            if not self._ssh_config:
                self.last_start_error = "SSH session settings are unavailable for restart"
                return False
            await self._shutdown_terminal()
            cfg = self._ssh_config
            ok = await self.start_ssh(
                host=str(cfg.get("host", "")),
                port=int(cfg.get("port", 22)),
                username=str(cfg.get("username", "")),
                password=str(cfg.get("password", "")),
                key_data=str(cfg.get("key_data", "")),
                cols=cols,
                rows=rows,
            )
            if ok:
                await self._reattach_clients_after_restart()
            return ok

        if not self._terminal:
            return False
        await self._shutdown_terminal()
        self._terminal = BridgedLocalTerminal(self.session_id)
        if not await self._terminal.start(cols, rows):
            return False
        await self._reattach_clients_after_restart()
        return True

    async def write(self, data: str) -> None:
        """将客户端输入写入底层终端。"""
        if self._terminal:
            await self._terminal.write(data)

    async def resize(self, cols: int, rows: int) -> None:
        """调整底层终端尺寸。"""
        if self._terminal:
            await self._terminal.resize(cols, rows)

    async def kill(self) -> None:
        """显式关闭终端会话并移出注册表。"""
        self.alive = False

        if self._terminal:
            await self._shutdown_terminal()

        self._client_callbacks.clear()

        if self._store:
            self._store.save(
                session_id=self.session_id,
                status="destroyed",
                kind=self.kind,
            )

        for ws in list(self._clients):
            try:
                if not ws.closed:
                    await ws.send_json({
                        "type": "session_closed",
                        "session_id": self.session_id,
                    })
            except (ConnectionError, RuntimeError):
                logger.debug("Failed to notify client of session close", exc_info=True)
            except Exception:
                logger.warning("Unexpected error notifying client of session close", exc_info=True)
        self._clients.clear()

        sessions_registry().pop(self.session_id, None)

    async def close(self) -> None:
        """关闭会话（kill 的别名）。"""
        await self.kill()


_sessions: Dict[str, TerminalSession] = {}


def sessions_registry() -> Dict[str, TerminalSession]:
    """返回活动会话注册表（仅供路由层与热重载清理使用）。"""
    return _sessions


def get_session(session_id: str) -> Optional[TerminalSession]:
    """按 ID 查找活动会话。"""
    return _sessions.get(session_id)


def list_sessions() -> List[TerminalSession]:
    """列出所有活动会话。"""
    return list(_sessions.values())


async def recover_sessions(store: TerminalSessionStore) -> None:
    """服务启动时从持久化存储恢复仍存活的终端会话。"""
    persist_dir = store.persist_dir
    if not persist_dir.exists():
        return

    def callback_factory(session_id: str) -> TerminalCallback:
        """公开方法 callback_factory。"""
        session = _sessions.get(session_id)
        if session:
            return TerminalCallback(
                on_output=session._broadcast_output,
                on_error=session._broadcast_error,
                on_exit=session._broadcast_exit,
                on_metadata=session._broadcast_metadata,
            )
        return TerminalCallback()

    recovered = await BridgedLocalTerminal.recover_sessions(persist_dir, callback_factory)
    now = time.time()

    for session_id, terminal in recovered.items():
        session = TerminalSession(session_id, "local")
        session._terminal = terminal
        session._store = store

        meta = store.load(session_id) if store else None
        if meta:
            session.name = meta.get("name")
            created_at = meta.get("created_at", 0)
            if terminal.alive and (now - created_at) > 86400:
                terminal.alive = False
                logger.warning(
                    "Session %s too old (age=%.0fs), treating as dead to avoid PID reuse",
                    session_id,
                    now - created_at,
                )

        session.alive = terminal.alive
        session.reattachable = False
        _sessions[session_id] = session

        if terminal.alive:
            logger.info("Recovered alive session (read-only): %s", session_id)
        else:
            logger.info("Recovered dead session: %s", session_id)


def resolve_cwd(raw: object) -> Optional[Path]:
    """解析工作目录路径，无效时返回 None。"""
    if not isinstance(raw, str) or not raw.strip():
        return None
    if "\x00" in raw:
        return None
    try:
        path = Path(raw.strip()).resolve()
    except (OSError, ValueError):
        return None
    if not path.is_dir():
        return None
    return path


def shell_cd_command(cwd: str) -> str:
    """构造切换工作目录的 shell 命令（含换行）。"""
    path = os.path.normpath(cwd.strip())
    if os.name == "nt":
        escaped = path.replace("'", "''")
        return f"Set-Location -LiteralPath '{escaped}'\r\n"
    escaped = path.replace("'", "'\\''")
    return f"cd '{escaped}'\n"
