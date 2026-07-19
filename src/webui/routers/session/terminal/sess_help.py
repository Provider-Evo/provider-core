from __future__ import annotations

"""终端会话恢复与 SSH/路径辅助函数（从 terminal_session.py 拆出）。"""

import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

from src.core.server.terminal.ssh_vault import get_ssh_vault
from src.foundation.logger import get_logger

logger = get_logger(__name__)


def resolve_cwd(raw: object) -> Optional[Path]:
    """解析并校验一个候选工作目录路径。"""
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
    """构造跨平台的 shell 切换目录命令。"""
    path = os.path.normpath(cwd.strip())
    if os.name == "nt":
        escaped = path.replace("'", "''")
        return "Set-Location -LiteralPath '{}'\r\n".format(escaped)
    escaped = path.replace("'", "'\\''")
    return "cd '{}'\n".format(escaped)


def resolve_ssh_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """从初始化 payload 或 vault connection_id 解析 SSH 连接字段。"""
    connection_id = payload.get("connection_id")
    if connection_id:
        creds = get_ssh_vault().resolve(str(connection_id))
        if creds:
            return {
                "host": creds["host"],
                "port": int(creds.get("port") or payload.get("port") or 22),
                "username": creds["username"],
                "password": creds.get("password", ""),
                "key_data": creds.get("key_data", ""),
                "connection_id": connection_id,
                "name": creds.get("name"),
            }
    return {
        "host": str(payload.get("host", "")),
        "port": int(payload.get("port", 22)),
        "username": str(payload.get("username", "")),
        "password": str(payload.get("password", "")),
        "key_data": str(payload.get("key_data", "")),
        "connection_id": connection_id,
        "name": payload.get("name"),
    }


def apply_recovered_metadata(
    session: Any, meta: Optional[Dict[str, Any]], terminal: Any, cfg: Any
) -> None:
    """将持久化元数据应用到恢复的会话，并判断是否因超龄而视为死亡。"""
    if not meta:
        return
    session.name = meta.get("name")
    created_at = meta.get("created_at", 0)
    if terminal.alive and (time.time() - created_at) > cfg.orphan_alive_hours * 3600:
        terminal.alive = False
        logger.warning(
            "Session %s too old (age=%.0fs), treating as dead",
            session.session_id,
            time.time() - created_at,
        )


def maybe_recover_tmux(
    session_id: str,
    meta: Optional[Dict[str, Any]],
    terminal: Any,
    cfg: Any,
    tmux_cls: type,
    tmux_available_fn: Any,
) -> Any:
    """若配置为 tmux 且当前恢复的进程已死，尝试改用 tmux 后端重建终端。"""
    backend = (meta or {}).get("backend", cfg.backend)
    if (
        backend != "tmux"
        or sys.platform == "win32"
        or not tmux_available_fn()
        or terminal.alive
    ):
        return terminal
    return terminal
