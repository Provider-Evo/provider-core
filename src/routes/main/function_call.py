"""函数调用处理路由。"""

from __future__ import annotations

import json
from typing import Any, Dict

import aiohttp.web

from src.logger import get_logger

__all__ = ["setup_routes"]
logger = get_logger(__name__)

_FUNCTION_REGISTRY: Dict[str, Dict[str, Any]] = {}


def register_function(name: str, description: str, parameters: Dict[str, Any]) -> None:
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
    app.router.add_post("/v1/function/call", _handle_function_call)
    app.router.add_get("/v1/functions", _list_functions)
