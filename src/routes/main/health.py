"""health 模块 — HTTP 入口路由。

职责：
    作为 Provider-Evo 项目标准模块，提供 health 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""



from __future__ import annotations

import aiohttp.web

from src.foundation.config import get_config

__all__ = ["setup_routes"]


async def _health_check(request: aiohttp.web.Request) -> aiohttp.web.Response:
    cfg = get_config()
    return aiohttp.web.json_response({"status": "ok", "version": cfg.server.version})


def setup_routes(app: aiohttp.web.Application) -> None:
    """公开方法 setup_routes。"""
    app.router.add_get("/health", _health_check)
