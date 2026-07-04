# -*- coding: utf-8 -*-
from __future__ import annotations

"""OpenAI 兼容路由——Stub/Not-Implemented 处理函数

包含所有返回 placeholder 响应的端点处理函数：
- Files (upload, list, retrieve, delete)
- Fine-Tuning
- Batch
- Assistants
- Threads
- Runs
- Vector Stores
- Uploads
"""

import time
import uuid

import aiohttp.web

from src.core.server import get_json as _get_json
from src.core.tools import normalize_content
from src.logger import get_logger
from src.routes.openai_helpers import (
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

__all__ = [
    "upload_file",
    "list_files",
    "retrieve_file",
    "delete_file",
    "retrieve_file_content",
    "create_fine_tuning_job",
    "list_fine_tuning_jobs",
    "retrieve_fine_tuning_job",
    "cancel_fine_tuning_job",
    "list_fine_tuning_events",
    "create_batch",
    "list_batches",
    "retrieve_batch",
    "cancel_batch",
    "create_assistant",
    "list_assistants",
    "retrieve_assistant",
    "modify_assistant",
    "delete_assistant",
    "create_thread",
    "retrieve_thread",
    "modify_thread",
    "delete_thread",
    "create_thread_message",
    "list_thread_messages",
    "create_run",
    "list_runs",
    "retrieve_run",
    "cancel_run",
    "submit_tool_outputs",
    "create_vector_store",
    "list_vector_stores",
    "retrieve_vector_store",
    "delete_vector_store",
    "create_vector_store_file",
    "list_vector_store_files",
    "create_upload",
    "add_upload_part",
    "complete_upload",
    "cancel_upload",
]

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
# Fine-tuning
# =======================================================================

async def create_fine_tuning_job(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """创建微调任务端点 /v1/fine_tuning/jobs。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _not_supported("Fine-tuning")


async def list_fine_tuning_jobs(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """微调任务列表端点 /v1/fine_tuning/jobs。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _json({"object": "list", "data": []})


async def retrieve_fine_tuning_job(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """获取微调任务详情端点 /v1/fine_tuning/jobs/{job_id}。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _err(404, "Job not found", "job_not_found")


async def cancel_fine_tuning_job(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """取消微调任务端点 /v1/fine_tuning/jobs/{job_id}/cancel。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _err(404, "Job not found", "job_not_found")


async def list_fine_tuning_events(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """微调任务事件列表端点 /v1/fine_tuning/jobs/{job_id}/events。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _json({"object": "list", "data": []})


# =======================================================================
# Batch
# =======================================================================

async def create_batch(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """创建批处理任务端点 /v1/batches。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _not_supported("Batch")


async def list_batches(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """批处理任务列表端点 /v1/batches。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _json({"object": "list", "data": []})


async def retrieve_batch(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """获取批处理任务详情端点 /v1/batches/{batch_id}。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _err(404, "Batch not found", "batch_not_found")


async def cancel_batch(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """取消批处理任务端点 /v1/batches/{batch_id}/cancel。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _err(404, "Batch not found", "batch_not_found")


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
    store_id = request.match_info["store_id"]
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
    store_id = request.match_info["store_id"]
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
    """添加上传分片端点 /v1/uploads/{upload_id}/parts。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
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
    """完成上传端点 /v1/uploads/{upload_id}/complete。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
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
    """取消上传端点 /v1/uploads/{upload_id}/cancel。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    upload_id = request.match_info["upload_id"]
    return _json({"id": upload_id, "object": "upload", "status": "cancelled"})
