from __future__ import annotations

"""终端实时输出桥接 — 子类化 echotools 会话，避免 monkey-patch。"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from echotools.terminal import LocalTerminal, SSHTerminal
from echotools.terminal.session import MAX_OFFLINE_BUFFER_BYTES, TerminalSession

__all__ = ["BridgedLocalTerminal", "BridgedSSHTerminal"]

_LOGGER = logging.getLogger(__name__)


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
    """SSH 终端：优先广播实时输出；仅密码登录时不尝试本机公钥/agent。"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._closing = False

    async def close(self) -> None:
        """优雅关闭 SSH，避免重启时 paramiko 报 socket 10054。"""
        self._closing = True
        self.alive = False

        await self._cancel_reader()

        channel = self._ssh_channel
        client = self._ssh_client
        self._ssh_channel = None
        self._ssh_client = None

        loop = asyncio.get_running_loop()
        if channel is not None:
            try:
                await loop.run_in_executor(None, self._graceful_close_channel, channel)
            except Exception:
                pass
        if client is not None:
            try:
                await loop.run_in_executor(None, self._graceful_close_client, client)
            except Exception:
                pass

        self._closing = False

    async def _fire_exit(self, code: int) -> None:
        """主动关闭时不向前端广播 exit，避免重启过程误报断开。"""
        if self._closing:
            return
        await TerminalSession._fire_exit(self, code)

    @staticmethod
    def _graceful_close_channel(channel: Any) -> None:
        try:
            if not channel.closed:
                channel.shutdown_write()
        except Exception:
            pass
        try:
            channel.close()
        except Exception:
            pass

    @staticmethod
    def _graceful_close_client(client: Any) -> None:
        try:
            transport = client.get_transport()
            if transport is not None and transport.is_active():
                transport.close()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass

    def save_state(self, persist_dir: Optional[Path] = None) -> None:
        """写入会话快照，供关停/热重载时持久化；合并已有元数据避免覆盖 ssh_config。"""
        if persist_dir is None:
            return

        persist_dir.mkdir(parents=True, exist_ok=True)
        meta_path = persist_dir / f"{self.session_id}.json"

        data: Dict[str, Any] = {}
        if meta_path.exists():
            try:
                data = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        now = time.time()
        data.update({
            "session_id": self.session_id,
            "pid": None,
            "cols": self.cols,
            "rows": self.rows,
            "kind": self.kind,
            "alive": self.is_alive,
            "status": "alive" if self.is_alive else data.get("status", "dead"),
            "updated_at": now,
        })
        if "created_at" not in data:
            data["created_at"] = now
        if not data.get("ssh_config"):
            data["ssh_config"] = {
                "host": self._host,
                "port": self._port,
                "username": self._username,
            }

        try:
            meta_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            _LOGGER.debug("Failed to save SSH session state", exc_info=True)

    async def start(self, cols: int = 80, rows: int = 24) -> bool:
        """连接远程 SSH；无私钥配置时强制密码认证，跳过 publickey。"""
        self.cols = cols
        self.rows = rows
        self._key_data = (self._key_data or "").strip() or None

        try:
            import paramiko
        except ImportError:
            await self._fire_error(
                "paramiko is not installed. "
                "Install it with: pip install paramiko>=3.0.0"
            )
            return False

        try:
            self._ssh_client = paramiko.SSHClient()
            self._ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            connect_kwargs: Dict[str, Any] = {
                "hostname": self._host,
                "port": self._port,
                "username": self._username,
                "timeout": 15,
            }

            if self._key_data:
                pkey = self._try_parse_key(paramiko, self._key_data)
                if pkey is None:
                    await self._fire_error(
                        "Failed to parse private key. "
                        "Supported formats: RSA, Ed25519, ECDSA."
                    )
                    return False
                connect_kwargs["pkey"] = pkey
            elif self._password:
                connect_kwargs["password"] = self._password
                connect_kwargs["look_for_keys"] = False
                connect_kwargs["allow_agent"] = False
            else:
                connect_kwargs["look_for_keys"] = True
                connect_kwargs["allow_agent"] = True

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, lambda: self._ssh_client.connect(**connect_kwargs)
            )

            transport = self._ssh_client.get_transport()
            if transport is None:
                await self._fire_error("SSH transport is unavailable")
                return False

            self._ssh_channel = transport.open_session()
            self._ssh_channel.get_pty(
                term="xterm-256color", width=cols, height=rows
            )
            self._ssh_channel.invoke_shell()
            self.alive = True

            self._reader_task = loop.create_task(self._read_ssh())
            return True

        except Exception as exc:
            await self._fire_error(f"SSH connection failed: {exc}")
            return False
