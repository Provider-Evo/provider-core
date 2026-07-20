
import time

import aiohttp.web

from src.core.server import get_json as _get_json
from src.foundation.logger import get_logger
from src.routes.openai.chat.helpers import (
    _err,
    _fid,
    _json,
    _vid,
)

logger = get_logger(__name__)

# =======================================================================
# Vector Stores
# =======================================================================


async def create_vector_store(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """创建向量存储端点 /v1/vector_stores。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    body = await _get_json(request) or {}
    return _json(
        {
            "id": _vid(),
            "object": "vector_store",
            "created_at": int(time.time()),
            "name": body.get("name", ""),
            "usage_bytes": 0,
            "file_counts": {
                "in_progress": 0,
                "completed": 0,
                "failed": 0,
                "cancelled": 0,
                "total": 0,
            },
            "status": "completed",
            "metadata": body.get("metadata", {}),
        }
    )


async def list_vector_stores(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """向量存储列表端点 /v1/vector_stores。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _json({"object": "list", "data": []})


async def retrieve_vector_store(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """获取向量存储详情端点 /v1/vector_stores/{store_id}。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _err(404, "Vector store not found", "not_found")


async def delete_vector_store(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """删除向量存储端点 /v1/vector_stores/{store_id}。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    store_id = request.match_info.get("vector_store_id") or request.match_info.get(
        "store_id", ""
    )
    return _json({"id": store_id, "object": "vector_store.deleted", "deleted": True})


async def create_vector_store_file(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """向量存储文件关联端点 /v1/vector_stores/{store_id}/files。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    store_id = request.match_info.get("vector_store_id") or request.match_info.get(
        "store_id", ""
    )
    return _json(
        {
            "id": _fid(),
            "object": "vector_store.file",
            "created_at": int(time.time()),
            "vector_store_id": store_id,
            "status": "completed",
        }
    )


async def list_vector_store_files(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """向量存储文件列表端点 /v1/vector_stores/{store_id}/files。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _json({"object": "list", "data": []})
