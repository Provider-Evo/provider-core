from __future__ import annotations

"""OpenAI 兼容路由 Stub 端点。"""

import time
import uuid

import aiohttp.web

from src.core.server import get_json as _get_json
from src.foundation.logger import get_logger
from src.routes.openai.helpers import (
    _aid,
    _err,
    _fid,
    _json,
    _not_supported,
    _rid,
    _tid,
    _uid,
    _vid,
)
from src.core.utils.compat.tools import normalize_content

logger = get_logger(__name__)

# =======================================================================
# Runs
# =======================================================================

async def create_run(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """创建运行端点 /v1/threads/{thread_id}/runs。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    thread_id = request.match_info["thread_id"]
    body = await _get_json(request) or {}
    return _json(
        {
            "id": _rid(),
            "object": "thread.run",
            "created_at": int(time.time()),
            "thread_id": thread_id,
            "assistant_id": body.get("assistant_id", ""),
            "status": "queued",
            "model": body.get("model", ""),
            "instructions": body.get("instructions"),
            "tools": body.get("tools", []),
            "metadata": body.get("metadata", {}),
        }
    )


async def list_runs(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """运行列表端点 /v1/threads/{thread_id}/runs。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _json({"object": "list", "data": []})


async def retrieve_run(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """获取运行详情端点 /v1/threads/{thread_id}/runs/{run_id}。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    thread_id = request.match_info["thread_id"]
    run_id = request.match_info["run_id"]
    return _json(
        {
            "id": run_id,
            "object": "thread.run",
            "created_at": int(time.time()),
            "thread_id": thread_id,
            "status": "completed",
            "model": "",
        }
    )


async def cancel_run(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """取消运行端点 /v1/threads/{thread_id}/runs/{run_id}/cancel。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    thread_id = request.match_info["thread_id"]
    run_id = request.match_info["run_id"]
    return _json(
        {
            "id": run_id,
            "object": "thread.run",
            "status": "cancelled",
            "thread_id": thread_id,
        }
    )


async def submit_tool_outputs(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """提交工具输出端点 /v1/threads/{thread_id}/runs/{run_id}/submit_tool_outputs。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    thread_id = request.match_info["thread_id"]
    run_id = request.match_info["run_id"]
    return _json(
        {
            "id": run_id,
            "object": "thread.run",
            "status": "completed",
            "thread_id": thread_id,
        }
    )
