"""function_call 模块 — HTTP 入口路由。

职责：
    作为 Provider-Evo 项目标准模块，提供 function_call 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""



from __future__ import annotations

import json
from typing import Any, Dict

import aiohttp.web

from src.foundation.logger import get_logger

__all__ = ["setup_routes"]
logger = get_logger(__name__)

_FUNCTION_REGISTRY: Dict[str, Dict[str, Any]] = {}


def register_function(name: str, description: str, parameters: Dict[str, Any]) -> None:
    """公开方法 register_function。"""
    _FUNCTION_REGISTRY[name] = {"name": name, "description": description, "parameters": parameters}


async def _handle_function_call(request: aiohttp.web.Request) -> aiohttp.web.Response:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return aiohttp.web.json_response({"error": {"message": "Invalid JSON"}}, status=400)
    function_name = body.get("name", "")
    arguments = body.get("arguments", {})
    if function_name not in _FUNCTION_REGISTRY:
        return aiohttp.web.json_response({"error": {"message": f"Unknown function: {function_name}"}}, status=404)
    result = {"name": function_name, "arguments": arguments, "output": f"Executed {function_name}"}
    return aiohttp.web.json_response(result)


async def _list_functions(request: aiohttp.web.Request) -> aiohttp.web.Response:
    return aiohttp.web.json_response({"functions": list(_FUNCTION_REGISTRY.values())})


def setup_routes(app: aiohttp.web.Application) -> None:
    """公开方法 setup_routes。"""
    app.router.add_post("/v1/function/call", _handle_function_call)
    app.router.add_get("/v1/functions", _list_functions)
