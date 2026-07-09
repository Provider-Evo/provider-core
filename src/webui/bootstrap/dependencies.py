from __future__ import annotations

"""WebUI 依赖解析。"""

from typing import Any, Optional

import aiohttp.web

from src.core.config import get_config
from src.core.server import REGISTRY_KEY
from src.webui.bootstrap.config_schema import PortableWebUISettings, WebUIServerConfig

__all__ = [
    "get_registry_from_request",
    "get_server_config",
    "get_portable_settings",
]


def get_registry_from_request(request: aiohttp.web.Request) -> Optional[Any]:
    """从请求中安全读取注册表。"""
    try:
        return request.app[REGISTRY_KEY]
    except Exception:
        return None


def get_server_config() -> WebUIServerConfig:
    """构建 WebUI 服务配置。"""
    config = get_config()
    return WebUIServerConfig(
        host=config.server.host,
        port=config.server.port,
    )


def get_portable_settings() -> PortableWebUISettings:
    """获取前端便携设置默认值。"""
    return PortableWebUISettings()
