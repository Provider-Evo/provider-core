
import time
import uuid

import aiohttp.web

from src.core.server import get_json as _get_json
from src.core.utils.compat.tools import normalize_content
from src.foundation.logger import get_logger
from src.routes.openai.chat.helpers import (
    _json,
    _tid,
)

logger = get_logger(__name__)

# =======================================================================
# Threads
# =======================================================================


async def create_thread(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """创建线程端点 /v1/threads。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _json(
        {
            "id": _tid(),
            "object": "thread",
            "created_at": int(time.time()),
            "metadata": {},
        }
    )


async def retrieve_thread(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """获取线程详情端点 /v1/threads/{thread_id}。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    thread_id = request.match_info["thread_id"]
    return _json(
        {
            "id": thread_id,
            "object": "thread",
            "created_at": int(time.time()),
            "metadata": {},
        }
    )


async def modify_thread(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """修改线程端点 /v1/threads/{thread_id}。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    thread_id = request.match_info["thread_id"]
    return _json(
        {
            "id": thread_id,
            "object": "thread",
            "created_at": int(time.time()),
            "metadata": {},
        }
    )


async def delete_thread(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """删除线程端点 /v1/threads/{thread_id}。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    thread_id = request.match_info["thread_id"]
    return _json({"id": thread_id, "object": "thread.deleted", "deleted": True})


async def create_thread_message(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """创建线程消息端点 /v1/threads/{thread_id}/messages。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    thread_id = request.match_info["thread_id"]
    body = await _get_json(request) or {}
    return _json(
        {
            "id": "msg_{}".format(uuid.uuid4().hex[:24]),
            "object": "thread.message",
            "created_at": int(time.time()),
            "thread_id": thread_id,
            "role": body.get("role", "user"),
            "content": [
                {
                    "type": "text",
                    "text": {
                        "value": normalize_content(body.get("content", "")),
                        "annotations": [],
                    },
                }
            ],
            "metadata": body.get("metadata", {}),
        }
    )


async def list_thread_messages(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """线程消息列表端点 /v1/threads/{thread_id}/messages。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _json({"object": "list", "data": []})
