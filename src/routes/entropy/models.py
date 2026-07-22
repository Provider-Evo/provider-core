# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from typing import Any, Dict, List

import aiohttp.web

from src.core.server import REGISTRY_KEY
from src.routes.openai.chat.helpers import _json


async def list_models(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/models。"""
    registry = request.app[REGISTRY_KEY]
    ct = int(time.time())
    models: List[Dict[str, Any]] = []
    if hasattr(registry, "list_models"):
        raw = await registry.list_models()
        for m in raw:
            model_id = m if isinstance(m, str) else m.get("id", "")
            if model_id:
                models.append(
                    {
                        "id": model_id,
                        "object": "model",
                        "created": ct,
                        "owned_by": "entropy",
                    }
                )
    return _json({"object": "list", "data": models})


async def retrieve_model(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/models/{model_id}。"""
    model_id = request.match_info.get("model_id", "")
    return _json(
        {
            "id": model_id,
            "object": "model",
            "created": int(time.time()),
            "owned_by": "entropy",
        }
    )


async def list_capabilities(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/capabilities。"""
    return _json({"object": "capabilities", "data": []})
