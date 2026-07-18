from __future__ import annotations

"""服务网络与代理配置。"""

from src.core.server.lifecycle.net.keys import REGISTRY_KEY, SESSION_KEY
from src.core.server.lifecycle.net.proxy import (
    activate,
    deactivate,
    get_proxy_dict,
    get_proxy_server,
    is_active,
)

__all__ = [
    "REGISTRY_KEY",
    "SESSION_KEY",
    "activate",
    "deactivate",
    "get_proxy_dict",
    "get_proxy_server",
    "is_active",
]
