# -*- coding: utf-8 -*-
from __future__ import annotations

"""OpenAI 兼容路由——聚合模块

本文件是一个轻量级聚合器，从子模块导入所有处理函数并注册路由。

子模块：
- openai_helpers: 共享工具函数、常量、ID 生成器
- openai_chat: Chat Completions 端点（流式 + 非流式）
- openai_media: 媒体端点（Images, Audio, Video, Embeddings, etc.）
- openai_stubs: Stub/Not-Implemented 处理函数
"""

import aiohttp.web

# -- 共享工具函数和常量 (re-exported for backward compatibility) --
from src.routes.openai_helpers import (  # noqa: F401
    _FNCALL_CLOSE_TAG,
    _FNCALL_END,
    _FNCALL_OPEN_TAG,
    _FNCALL_START,
    _aid,
    _bid,
    _cid,
    _err,
    _extract_upload_files,
    _fid,
    _id,
    _json,
    _mime_to_ext,
    _normalize_messages,
    _not_supported,
    _rid,
    _sl,
    _tid,
    _uid,
    _vid,
)

# -- Chat Completions --
from src.routes.openai_chat import (  # noqa: F401
    _stream_chat,
    chat_completions,
)

# -- 媒体端点 --
from src.routes.openai_media import (  # noqa: F401
    create_audio_translation,
    create_embeddings,
    create_image,
    create_image_variation,
    create_moderation,
    create_rerank,
    create_response,
    create_speech,
    create_transcription,
    create_video,
    edit_image,
)

# -- Stub / Not-Implemented 处理函数 --
from src.routes.openai_stubs import (  # noqa: F401
    add_upload_part,
    cancel_batch,
    cancel_fine_tuning_job,
    cancel_run,
    cancel_upload,
    complete_upload,
    create_assistant,
    create_batch,
    create_fine_tuning_job,
    create_run,
    create_thread,
    create_thread_message,
    create_upload,
    create_vector_store,
    create_vector_store_file,
    delete_assistant,
    delete_file,
    delete_thread,
    delete_vector_store,
    list_assistants,
    list_batches,
    list_files,
    list_fine_tuning_events,
    list_fine_tuning_jobs,
    list_runs,
    list_thread_messages,
    list_vector_store_files,
    list_vector_stores,
    modify_assistant,
    modify_thread,
    retrieve_assistant,
    retrieve_batch,
    retrieve_file,
    retrieve_file_content,
    retrieve_fine_tuning_job,
    retrieve_run,
    retrieve_thread,
    retrieve_vector_store,
    submit_tool_outputs,
    upload_file,
)

from src.logger import get_logger

__all__ = [
    # 路由注册
    "setup_routes",
    # 共享工具函数 (backward compatibility)
    "_id",
    "_cid",
    "_bid",
    "_fid",
    "_aid",
    "_tid",
    "_rid",
    "_vid",
    "_uid",
    "_json",
    "_err",
    "_not_supported",
    "_normalize_messages",
    "_extract_upload_files",
    "_mime_to_ext",
    "_sl",
    "_FNCALL_START",
    "_FNCALL_END",
    "_FNCALL_OPEN_TAG",
    "_FNCALL_CLOSE_TAG",
    # Chat Completions
    "_stream_chat",
    "chat_completions",
    # 媒体端点
    "create_response",
    "create_embeddings",
    "create_image",
    "edit_image",
    "create_image_variation",
    "create_speech",
    "create_transcription",
    "create_audio_translation",
    "create_video",
    "create_moderation",
    "create_rerank",
    # Stub 处理函数
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


# ════════════════════════════════════════════════════════════════
# 路由注册
# ════════════════════════════════════════════════════════════════


def setup_routes(app: aiohttp.web.Application) -> None:
    """注册所有 OpenAI 兼容路由。

    Args:
        app: aiohttp.web.Application 实例。
    """
    app.router.add_route("*", "/v1/chat/completions", chat_completions)
    app.router.add_post("/v1/responses", create_response)
    app.router.add_post("/v1/embeddings", create_embeddings)
    app.router.add_post("/v1/images/generations", create_image)
    app.router.add_post("/v1/images/edits", edit_image)
    app.router.add_post("/v1/images/variations", create_image_variation)
    app.router.add_post("/v1/audio/speech", create_speech)
    app.router.add_post("/v1/audio/transcriptions", create_transcription)
    app.router.add_post("/v1/audio/translations", create_audio_translation)
    app.router.add_post("/v1/videos/generations", create_video)
    app.router.add_post("/v1/moderations", create_moderation)
    app.router.add_post("/v1/rerank", create_rerank)
    app.router.add_post("/v1/files", upload_file)
    app.router.add_get("/v1/files", list_files)
    app.router.add_get("/v1/files/{file_id}", retrieve_file)
    app.router.add_delete("/v1/files/{file_id}", delete_file)
    app.router.add_get("/v1/files/{file_id}/content", retrieve_file_content)
    app.router.add_post("/v1/fine_tuning/jobs", create_fine_tuning_job)
    app.router.add_get("/v1/fine_tuning/jobs", list_fine_tuning_jobs)
    app.router.add_get("/v1/fine_tuning/jobs/{job_id}", retrieve_fine_tuning_job)
    app.router.add_post("/v1/fine_tuning/jobs/{job_id}/cancel", cancel_fine_tuning_job)
    app.router.add_get("/v1/fine_tuning/jobs/{job_id}/events", list_fine_tuning_events)
    app.router.add_post("/v1/batches", create_batch)
    app.router.add_get("/v1/batches", list_batches)
    app.router.add_get("/v1/batches/{batch_id}", retrieve_batch)
    app.router.add_post("/v1/batches/{batch_id}/cancel", cancel_batch)
    app.router.add_post("/v1/assistants", create_assistant)
    app.router.add_get("/v1/assistants", list_assistants)
    app.router.add_get("/v1/assistants/{assistant_id}", retrieve_assistant)
    app.router.add_post("/v1/assistants/{assistant_id}", modify_assistant)
    app.router.add_delete("/v1/assistants/{assistant_id}", delete_assistant)
    app.router.add_post("/v1/threads", create_thread)
    app.router.add_get("/v1/threads/{thread_id}", retrieve_thread)
    app.router.add_post("/v1/threads/{thread_id}", modify_thread)
    app.router.add_delete("/v1/threads/{thread_id}", delete_thread)
    app.router.add_post("/v1/threads/{thread_id}/messages", create_thread_message)
    app.router.add_get("/v1/threads/{thread_id}/messages", list_thread_messages)
    app.router.add_post("/v1/threads/{thread_id}/runs", create_run)
    app.router.add_get("/v1/threads/{thread_id}/runs", list_runs)
    app.router.add_get("/v1/threads/{thread_id}/runs/{run_id}", retrieve_run)
    app.router.add_post("/v1/threads/{thread_id}/runs/{run_id}/cancel", cancel_run)
    app.router.add_post(
        "/v1/threads/{thread_id}/runs/{run_id}/submit_tool_outputs", submit_tool_outputs
    )
    app.router.add_post("/v1/vector_stores", create_vector_store)
    app.router.add_get("/v1/vector_stores", list_vector_stores)
    app.router.add_get("/v1/vector_stores/{store_id}", retrieve_vector_store)
    app.router.add_delete("/v1/vector_stores/{store_id}", delete_vector_store)
    app.router.add_post("/v1/vector_stores/{store_id}/files", create_vector_store_file)
    app.router.add_get("/v1/vector_stores/{store_id}/files", list_vector_store_files)
    app.router.add_post("/v1/uploads", create_upload)
    app.router.add_post("/v1/uploads/{upload_id}/parts", add_upload_part)
    app.router.add_post("/v1/uploads/{upload_id}/complete", complete_upload)
    app.router.add_post("/v1/uploads/{upload_id}/cancel", cancel_upload)
