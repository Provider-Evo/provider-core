from __future__ import annotations

"""终端会话注册表 — 全局 session_id -> TerminalSession 映射。"""

from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.webui.routers.session.terminal.session_all.base import TerminalSession

_sessions: "Dict[str, TerminalSession]" = {}


def sessions_registry() -> "Dict[str, TerminalSession]":
    return _sessions


def get_session(session_id: str) -> "Optional[TerminalSession]":
    return _sessions.get(session_id)


def list_sessions() -> "List[TerminalSession]":
    return list(_sessions.values())
