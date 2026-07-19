from __future__ import annotations

"""WebUI 终端会话状态机 — 兼容导入 shim。

实际实现已拆分至 ``session/`` 子包（base/lifecycle/clients/broadcast/registry/recover），
本文件仅保留原有公共导入路径，避免破坏既有引用。
"""

from src.webui.routers.session.terminal.sess_help import (
    resolve_cwd,
    resolve_ssh_from_payload,
    shell_cd_command,
)
from src.webui.routers.session.terminal.session_all.base import TerminalSession
from src.webui.routers.session.terminal.session_all.recover import recover_sessions
from src.webui.routers.session.terminal.session_all.reg import (
    get_session,
    list_sessions,
    sessions_registry,
)

__all__ = [
    "TerminalSession",
    "get_session",
    "list_sessions",
    "recover_sessions",
    "resolve_cwd",
    "resolve_ssh_from_payload",
    "sessions_registry",
    "shell_cd_command",
]
