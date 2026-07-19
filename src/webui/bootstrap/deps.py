"""dependencies 模块 — WebUI 层。

职责：
    作为 Provider-Evo 项目标准模块，提供 dependencies 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""

from typing import Any, Optional

import aiohttp.web

from src.core.server import REGISTRY_KEY
from src.foundation.config import get_config
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
