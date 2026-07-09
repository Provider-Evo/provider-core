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
# Assistants
# =======================================================================

async def create_assistant(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """创建助手端点 /v1/assistants。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    body = await _get_json(request) or {}
    return _json(
        {
            "id": _aid(),
            "object": "assistant",
            "created_at": int(time.time()),
            "name": body.get("name"),
            "description": body.get("description"),
            "model": body.get("model", ""),
            "instructions": body.get("instructions"),
            "tools": body.get("tools", []),
            "metadata": body.get("metadata", {}),
        }
    )


async def list_assistants(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """助手列表端点 /v1/assistants。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _json({"object": "list", "data": []})


async def retrieve_assistant(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """获取助手详情端点 /v1/assistants/{assistant_id}。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _err(404, "Assistant not found", "assistant_not_found")


async def modify_assistant(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """修改助手端点 /v1/assistants/{assistant_id}。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _err(404, "Assistant not found", "assistant_not_found")


async def delete_assistant(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """删除助手端点 /v1/assistants/{assistant_id}。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    assistant_id = request.match_info["assistant_id"]
    return _json(
        {
            "id": assistant_id,
            "object": "assistant.deleted",
            "deleted": True,
        }
    )
