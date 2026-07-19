from __future__ import annotations

"""终端会话恢复 — 服务启动时从持久化存储恢复仍存活的会话。"""

import sys
import time

from echotools.terminal import TerminalCallback

from src.core.server.terminal.sess import TerminalSessionStore
from src.foundation.config import get_config
from src.foundation.logger import get_logger
from src.webui.routers.session.terminal.out_bridge import (
    BridgedLocalTerminal,
    BridgedTmuxTerminal,
)
from src.webui.routers.session.terminal.sess_help import apply_recovered_metadata
from src.webui.routers.session.terminal.session_all.base import TerminalSession
from src.webui.routers.session.terminal.session_all.reg import sessions_registry

try:
    from echotools.terminal.tmux import tmux_available
except ImportError:
    import shutil

    def tmux_available() -> bool:
        if sys.platform == "win32":
            return False
        return shutil.which("tmux") is not None


logger = get_logger(__name__)


def _callback_factory(session_id: str) -> TerminalCallback:
    session = sessions_registry().get(session_id)
    if session:
        return TerminalCallback(
            on_output=session._broadcast_output,
            on_error=session._broadcast_error,
            on_exit=session._broadcast_exit,
            on_metadata=session._broadcast_metadata,
        )
    return TerminalCallback()


async def _maybe_switch_to_tmux(
    session: TerminalSession, session_id: str, meta, cfg, terminal
):
    """若配置为 tmux 且当前恢复的进程已死，尝试改用 tmux 后端重建终端。"""
    backend = (meta or {}).get("backend", cfg.backend)
    if (
        backend != "tmux"
        or sys.platform == "win32"
        or not tmux_available()
        or terminal.alive
    ):
        return terminal
    tmux_term = BridgedTmuxTerminal(session_id)
    if await tmux_term.start(
        meta.get("cols", 80) if meta else 80,
        meta.get("rows", 24) if meta else 24,
    ):
        session._terminal = tmux_term
        return tmux_term
    return terminal


async def recover_sessions(store: TerminalSessionStore) -> None:
    """服务启动时从持久化存储恢复仍存活的终端会话。"""
    cfg = get_config().terminal
    persist_dir = store.persist_dir
    if not persist_dir.exists():
        return

    store.cleanup_stale(
        destroyed_max_age_seconds=cfg.orphan_destroyed_days * 86400,
        alive_max_age_seconds=cfg.orphan_alive_hours * 3600,
    )

    recovered = await BridgedLocalTerminal.recover_sessions(
        persist_dir, _callback_factory
    )
    registry = sessions_registry()

    for session_id, terminal in recovered.items():
        meta = store.load(session_id) if store else None
        kind = (meta or {}).get("kind", "local")
        session = TerminalSession(session_id, kind)
        session._terminal = terminal
        session._store = store

        apply_recovered_metadata(session, meta, terminal, cfg)
        terminal = await _maybe_switch_to_tmux(session, session_id, meta, cfg, terminal)

        session.alive = terminal.alive
        session.readonly = not terminal.alive
        session.reattachable = terminal.alive
        if terminal.alive:
            session._ensure_writer()
        else:
            session.reattachable = False

        registry[session_id] = session
        if terminal.alive:
            logger.info("Recovered alive session: %s", session_id)
        else:
            logger.info("Recovered dead session (readonly): %s", session_id)
