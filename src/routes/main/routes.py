"""routes 模块 — HTTP 入口路由。

职责：
    作为 Provider-Evo 项目标准模块，提供 routes 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""

# src/routes/main/routes.py
"""主路由——健康检查、模型列表、状态、能力矩阵、函数调用。"""

import aiohttp.web

from src.routes.main.func_call import setup_routes as setup_function_call  # noqa: F401
from src.routes.main.static import setup_routes as setup_static  # noqa: F401

__all__ = ["setup_routes"]


def setup_routes(app: aiohttp.web.Application) -> None:
    """注册所有主路由。

    Args:
        app: aiohttp.web.Application 实例。
    """
    setup_static(app)
    setup_function_call(app)
