from __future__ import annotations

# src/routes/main/routes.py
"""主路由——健康检查、模型列表、状态、能力矩阵、函数调用。"""

import aiohttp.web

from src.routes.main.static import setup_routes as setup_static  # noqa: F401
from src.routes.main.function_call import setup_routes as setup_function_call  # noqa: F401

__all__ = ["setup_routes"]


def setup_routes(app: aiohttp.web.Application) -> None:
    """注册所有主路由。

    Args:
        app: aiohttp.web.Application 实例。
    """
    setup_static(app)
    setup_function_call(app)
