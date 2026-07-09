from __future__ import annotations

"""OpenAI 兼容路由 Stub 端点。"""

import time
import uuid

import aiohttp.web

from src.core.server import get_json as _get_json
from src.logger import get_logger
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
# Files
# =======================================================================

async def upload_file(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """文件上传端点 /v1/files。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    fid = _fid()
    filename = "unknown"
    purpose = "assistants"
    file_bytes = 0

    content_type = request.content_type or ""
    if "multipart" in content_type:
        try:
            reader = await request.multipart()
            async for field in reader:
                if field.name == "file":
                    data = await field.read()
                    file_bytes = len(data)
                    filename = field.filename or "unknown"
                elif field.name == "purpose":
                    purpose = (await field.read()).decode("utf-8")
        except Exception as exc:
            logger.debug("解析 multipart 上传字段失败，使用默认元数据: %s", exc)

    return _json(
        {
            "id": fid,
            "object": "file",
            "bytes": file_bytes,
            "created_at": int(time.time()),
            "filename": filename,
            "purpose": purpose,
            "status": "uploaded",
        }
    )


async def list_files(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """文件列表端点 /v1/files。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _json({"object": "list", "data": []})


async def retrieve_file(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """获取文件详情端点 /v1/files/{file_id}。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    file_id = request.match_info["file_id"]
    return _json(
        {
            "id": file_id,
            "object": "file",
            "bytes": 0,
            "created_at": int(time.time()),
            "filename": "unknown",
            "purpose": "assistants",
        }
    )


async def delete_file(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """删除文件端点 /v1/files/{file_id}。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    file_id = request.match_info["file_id"]
    return _json({"id": file_id, "object": "file", "deleted": True})


async def retrieve_file_content(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """获取文件内容端点 /v1/files/{file_id}/content。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _err(404, "File not found", "file_not_found")


# =======================================================================
# Uploads
# =======================================================================

async def create_upload(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """创建上传端点 /v1/uploads。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    body = await _get_json(request) or {}
    return _json(
        {
            "id": _uid(),
            "object": "upload",
            "bytes": body.get("bytes", 0),
            "created_at": int(time.time()),
            "filename": body.get("filename", ""),
            "purpose": body.get("purpose", ""),
            "status": "pending",
        }
    )


async def add_upload_part(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """添加上传分片端点 /v1/uploads/{upload_id}/parts。"""
    upload_id = request.match_info["upload_id"]
    return _json(
        {
            "id": "part_{}".format(uuid.uuid4().hex[:16]),
            "object": "upload.part",
            "created_at": int(time.time()),
            "upload_id": upload_id,
        }
    )


async def complete_upload(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """完成上传端点 /v1/uploads/{upload_id}/complete。"""
    upload_id = request.match_info["upload_id"]
    return _json(
        {
            "id": upload_id,
            "object": "upload",
            "status": "completed",
            "file": {
                "id": _fid(),
                "object": "file",
                "created_at": int(time.time()),
            },
        }
    )


async def cancel_upload(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """取消上传端点 /v1/uploads/{upload_id}/cancel。"""
    upload_id = request.match_info["upload_id"]
    return _json({"id": upload_id, "object": "upload", "status": "cancelled"})

