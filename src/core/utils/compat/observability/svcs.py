
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, List, Optional

import aiohttp.web
from aiohttp.web_app import AppKey

__all__ = [
    "OBSERVABILITY_KEY",
    "ObservabilityServices",
    "get_observability_services",
    "set_observability_services",
]

OBSERVABILITY_KEY: AppKey["ObservabilityServices"] = AppKey("observability")

BroadcastFn = Callable[[dict[str, Any]], Awaitable[None]]
PushEventFn = Callable[[dict[str, Any]], None]
VoidFn = Callable[[], None]
RecoverSessionsFn = Callable[[Any], Awaitable[None]]
ListSessionsFn = Callable[[], List[Any]]
SetupLogsFn = Callable[[], None]
SetLoopFn = Callable[[Any], None]


async def _async_noop(*_args: Any, **_kwargs: Any) -> None:
    return None


async def _async_empty_list(*_args: Any, **_kwargs: Any) -> List[Any]:
    return []


@dataclass
class ObservabilityServices:
    """WebUI 观测能力的可注入实现（默认 no-op）。"""

    start_stats_persist: VoidFn = field(default=lambda: None)
    save_stats: VoidFn = field(default=lambda: None)
    start_request_persist: Callable[[], Awaitable[None]] = field(default=_async_noop)
    save_requests: VoidFn = field(default=lambda: None)
    setup_loguru_sink: SetupLogsFn = field(default=lambda: None)
    set_log_broker_loop: SetLoopFn = field(default=lambda _loop: None)
    broadcast_log: BroadcastFn = field(default=_async_noop)
    push_request_event: PushEventFn = field(default=lambda _event: None)
    recover_terminal_sessions: RecoverSessionsFn = field(default=_async_noop)
    list_terminal_sessions: ListSessionsFn = field(default=list)
    save_terminal_states: Callable[[], None] = field(default=lambda: None)
    close_log_sockets: Callable[[], Awaitable[List[aiohttp.web.WebSocketResponse]]] = (
        field(
            default=_async_empty_list,
        )
    )
    close_terminal_sockets: Callable[
        [], Awaitable[List[aiohttp.web.WebSocketResponse]]
    ] = field(
        default=_async_empty_list,
    )
    close_request_monitor_sockets: Callable[
        [], Awaitable[List[aiohttp.web.WebSocketResponse]]
    ] = field(
        default=_async_empty_list,
    )
    request_broker_sockets: Optional[List[Any]] = None


_services: ObservabilityServices = ObservabilityServices()


def set_observability_services(services: ObservabilityServices) -> None:
    """注册全局观测实现（Runner 启动时由 bootstrap 调用）。"""
    global _services
    _services = services


def get_observability_services() -> ObservabilityServices:
    """获取当前观测实现。"""
    return _services


def observability_from_app(app: Any) -> ObservabilityServices:
    """从 aiohttp app 读取观测服务，缺省回退全局注册表。"""
    try:
        return app[OBSERVABILITY_KEY]
    except KeyError:
        return get_observability_services()
