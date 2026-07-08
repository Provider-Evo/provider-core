from __future__ import annotations

import aiohttp.web

__all__ = ["setup_routes"]

_MODELS = [
    {"id": "qwen-turbo", "object": "model", "created": 1700000000, "owned_by": "qwen"},
    {"id": "qwen-plus", "object": "model", "created": 1700000001, "owned_by": "qwen"},
    {"id": "deepseek-chat", "object": "model", "created": 1700000002, "owned_by": "deepseek"},
    {"id": "deepseek-coder", "object": "model", "created": 1700000003, "owned_by": "deepseek"},
]


async def _list_models(request: aiohttp.web.Request) -> aiohttp.web.Response:
    return aiohttp.web.json_response({"object": "list", "data": _MODELS})


async def _get_model(request: aiohttp.web.Request) -> aiohttp.web.Response:
    model_id = request.match_info.get("model", "")
    for m in _MODELS:
        if m["id"] == model_id:
            return aiohttp.web.json_response(m)
    return aiohttp.web.json_response({"error": {"message": f"Model not found: {model_id}"}}, status=404)


def setup_routes(app: aiohttp.web.Application) -> None:
    app.router.add_get("/v1/models", _list_models)
    app.router.add_get("/v1/models/{model}", _get_model)
