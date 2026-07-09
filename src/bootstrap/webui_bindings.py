from __future__ import annotations

"""将 WebUI 观测实现注册到 core.observability。"""

import asyncio
from typing import Any, List

import aiohttp.web

from src.core.auth.session import register_session_verifier
from src.core.observability import ObservabilityServices, set_observability_services


def register_webui_bindings() -> ObservabilityServices:
    """构建并注册 WebUI 观测与会话校验实现。"""
    from src.core.server.infra.terminal_sessions import get_terminal_store
    from src.webui.core.logs_ws import log_broker, setup_loguru_sink
    from src.webui.core.security import token_manager
    from src.webui.routers.session.terminal import list_sessions, recover_sessions
    from src.webui.services.request_log import (
        request_broker,
        save_requests,
        start_request_persist,
    )
    from src.webui.services.stats import save_stats, start_persist

    register_session_verifier(token_manager.verify)

    async def _close_log_sockets() -> List[aiohttp.web.WebSocketResponse]:
        async with log_broker._lock:
            sockets = list(log_broker._sockets)
            log_broker._sockets.clear()
        return sockets

    async def _close_terminal_sockets() -> List[aiohttp.web.WebSocketResponse]:
        sockets: list[aiohttp.web.WebSocketResponse] = []
        for session in list_sessions():
            sockets.extend(list(session._clients))
        return sockets

    async def _close_request_monitor_sockets() -> List[aiohttp.web.WebSocketResponse]:
        broker_sockets = getattr(request_broker, "_sockets", None)
        if broker_sockets is None:
            return []
        sockets = list(broker_sockets)
        broker_sockets.clear()
        return sockets

    async def _recover_terminal_sessions(_registry: Any) -> None:
        await recover_sessions(get_terminal_store())

    def _save_terminal_states() -> None:
        store = get_terminal_store()
        for session_obj in list_sessions():
            if session_obj._terminal and session_obj.alive:
                session_obj._terminal.save_state(store.persist_dir)

    async def _broadcast_log(payload: dict[str, Any]) -> None:
        await log_broker.broadcast(payload)

    services = ObservabilityServices(
        start_stats_persist=start_persist,
        save_stats=save_stats,
        start_request_persist=start_request_persist,
        save_requests=save_requests,
        setup_loguru_sink=setup_loguru_sink,
        set_log_broker_loop=log_broker.set_loop,
        broadcast_log=_broadcast_log,
        push_request_event=request_broker.push_event,
        recover_terminal_sessions=_recover_terminal_sessions,
        list_terminal_sessions=list_sessions,
        save_terminal_states=_save_terminal_states,
        close_log_sockets=_close_log_sockets,
        close_terminal_sockets=_close_terminal_sockets,
        close_request_monitor_sockets=_close_request_monitor_sockets,
        request_broker_sockets=getattr(request_broker, "_sockets", None),
    )
    set_observability_services(services)
    return services


def log_webui_token_if_enabled() -> None:
    """鉴权开启时在日志中输出 WebUI token。"""
    from src.core.config import get_config
    from src.logger import get_logger

    cfg = get_config()
    if not cfg.auth.enabled:
        return
    from src.webui.core.security import token_manager

    logger = get_logger(__name__)
    token = token_manager.token
    logger.info("WebUI Token: %s", token)
