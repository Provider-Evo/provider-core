"""webui_bindings 模块 — 项目标准模块。

职责：
    作为 Provider-Evo 项目标准模块，提供 webui_bindings 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""

from __future__ import annotations

import asyncio
from typing import Any, List

import aiohttp.web

from src.core.server.http.auth.session import register_session_verifier
from src.core.utils.compat.observability import ObservabilityServices, set_observability_services


def _build_socket_closers(log_broker: Any, list_sessions: Any, request_broker: Any) -> Any:
    """组装用于关闭各类 WebSocket 连接的回调闭包，返回三元组。"""

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

    return _close_log_sockets, _close_terminal_sockets, _close_request_monitor_sockets


def _build_observability_services() -> ObservabilityServices:
    """组装 ObservabilityServices 所需的各类观测回调闭包。"""
    from src.core.server.terminal.sess import get_terminal_store
    from src.webui.internal.core.logs_ws import log_broker, setup_loguru_sink
    from src.webui.routers.session.terminal.session_all.term import list_sessions, recover_sessions
    from src.webui.data.services.logs.request_log import (
        request_broker,
        save_requests,
        start_request_persist,
    )
    from src.webui.data.services.stats import save_stats, start_persist

    _close_log_sockets, _close_terminal_sockets, _close_request_monitor_sockets = _build_socket_closers(
        log_broker, list_sessions, request_broker
    )

    async def _recover_terminal_sessions(_registry: Any) -> None:
        await recover_sessions(get_terminal_store())

    def _save_terminal_states() -> None:
        store = get_terminal_store()
        for session_obj in list_sessions():
            if session_obj._terminal and session_obj.alive:
                session_obj._terminal.save_state(store.persist_dir)

    async def _broadcast_log(payload: dict[str, Any]) -> None:
        await log_broker.broadcast(payload)

    return ObservabilityServices(
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


def register_webui_bindings() -> ObservabilityServices:
    """构建并注册 WebUI 观测与会话校验实现。"""
    from src.webui.internal.core.secure import token_manager

    register_session_verifier(token_manager.verify)
    services = _build_observability_services()
    set_observability_services(services)
    return services


def log_webui_token_if_enabled() -> None:
    """鉴权开启时在日志中输出 WebUI token。"""
    from src.foundation.config import get_config
    from src.foundation.logger import get_logger

    cfg = get_config()
    if not cfg.auth.enabled:
        return
    from src.webui.internal.core.secure import token_manager

    logger = get_logger(__name__)
    token = token_manager.token
    logger.info("WebUI Token: %s", token)
