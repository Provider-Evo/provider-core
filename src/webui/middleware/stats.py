from __future__ import annotations

"""请求统计中间件 — 自动记录每次 API 请求的指标。"""

import time
from typing import Callable

import aiohttp.web

from src.webui.services.stats import get_stats

__all__ = ["stats_middleware"]


_API_PREFIXES = ("/v1/chat/", "/v1/completions", "/v1/messages", "/v1/models", "/v1/embeddings")


@aiohttp.web.middleware
async def stats_middleware(
    request: aiohttp.web.Request,
    handler: Callable,
) -> aiohttp.web.StreamResponse:
    """记录 API 请求统计。"""
    path = request.path

    if not any(path.startswith(p) for p in _API_PREFIXES):
        return await handler(request)

    start = time.monotonic()
    status = 200
    platform = ""
    model = ""

    try:
        if request.method == "POST" and request.content_type == "application/json":
            try:
                body = await request.json()
                model = body.get("model", "")
            except Exception:
                pass
    except Exception:
        pass

    try:
        response = await handler(request)
        status = response.status
        if hasattr(response, "_platform"):
            platform = response._platform
        return response
    except aiohttp.web.HTTPException as exc:
        status = exc.status
        raise
    except Exception:
        status = 500
        raise
    finally:
        latency_ms = (time.monotonic() - start) * 1000
        get_stats().record(
            platform=platform,
            model=model,
            status=status,
            latency_ms=latency_ms,
        )
