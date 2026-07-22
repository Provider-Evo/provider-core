# -*- coding: utf-8 -*-
from __future__ import annotations

"""OpenAI 兼容路由——聚合模块

本文件是一个轻量级聚合器，从子模块导入所有处理函数并注册路由。

子模块：
- helpers: 共享工具函数、常量、ID 生成器
- chat: Chat Completions 端点（流式 + 非流式）
- completions: 遗留 Completions API
- responses_api: Responses API 及子资源
- media: 媒体端点（Images, Audio, Embeddings, etc.）
- videos: Videos API 官方路径
- chat_stored: Chat Completions 存储子资源
- catalog: 官方 route_catalog 批量 stub 注册
- stubs: Stub/Not-Implemented 处理函数
"""

import aiohttp.web

from src.foundation.logger import get_logger
from src.routes.shared.prefix import oai_path as _p
from src.routes.openai.catalog.catalog import register_catalog_routes
from src.routes.openai.chat import _stream_chat, chat_completions  # noqa: F401
from src.routes.openai.chat.compl import completions
from src.routes.openai.chat.helpers import (  # noqa: F401
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
from src.routes.openai.chat.stored import (
    delete_stored_completion,
    list_stored_completion_messages,
    retrieve_stored_completion,
    update_stored_completion,
)
from src.routes.openai.media import (
    create_audio_translation,
    create_embeddings,
    create_image,
    create_image_variation,
    create_moderation,
    create_rerank,
    create_speech,
    create_transcription,
    edit_image,
)
from src.routes.openai.media.videos import (
    create_video,
    create_video_character,
    create_video_edit,
    create_video_extension,
    delete_video,
    legacy_video_generations,
    list_videos,
    remix_video,
    retrieve_video,
    retrieve_video_character,
    retrieve_video_content,
)
from src.routes.openai.resp_api import (
    cancel_response,
    compact_responses,
    count_input_tokens,
    create_response,
    delete_response,
    list_input_items,
    retrieve_response,
)
from src.routes.main.static import get_model, list_models
from src.routes.openai.stubs import (
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

logger = get_logger(__name__)

__all__ = ["setup_routes"]


def _register_openai_core_routes(app: aiohttp.web.Application) -> None:
    app.router.add_route("*", _p("/v1/chat/completions"), chat_completions)
    app.router.add_post(_p("/v1/completions"), completions)
    app.router.add_post(_p("/v1/responses"), create_response)
    app.router.add_get(_p("/v1/responses/{response_id}"), retrieve_response)
    app.router.add_delete(_p("/v1/responses/{response_id}"), delete_response)
    app.router.add_post(_p("/v1/responses/{response_id}/cancel"), cancel_response)
    app.router.add_get(_p("/v1/responses/{response_id}/input_items"), list_input_items)
    app.router.add_post(_p("/v1/responses/compact"), compact_responses)
    app.router.add_post(_p("/v1/responses/input_tokens"), count_input_tokens)
    app.router.add_post(_p("/v1/embeddings"), create_embeddings)
    app.router.add_post(_p("/v1/images/generations"), create_image)
    app.router.add_post(_p("/v1/images/edits"), edit_image)
    app.router.add_post(_p("/v1/images/variations"), create_image_variation)
    app.router.add_post(_p("/v1/audio/speech"), create_speech)
    app.router.add_post(_p("/v1/audio/transcriptions"), create_transcription)
    app.router.add_post(_p("/v1/audio/translations"), create_audio_translation)
    app.router.add_post(_p("/v1/videos"), create_video)
    app.router.add_get(_p("/v1/videos"), list_videos)
    app.router.add_get(_p("/v1/videos/{video_id}"), retrieve_video)
    app.router.add_delete(_p("/v1/videos/{video_id}"), delete_video)
    app.router.add_get(_p("/v1/videos/{video_id}/content"), retrieve_video_content)
    app.router.add_post(_p("/v1/videos/{video_id}/remix"), remix_video)
    app.router.add_post(_p("/v1/videos/characters"), create_video_character)
    app.router.add_get(_p("/v1/videos/characters/{character_id}"), retrieve_video_character)
    app.router.add_post(_p("/v1/videos/edits"), create_video_edit)
    app.router.add_post(_p("/v1/videos/extensions"), create_video_extension)
    app.router.add_post(_p("/v1/videos/generations"), legacy_video_generations)
    app.router.add_post(_p("/v1/moderations"), create_moderation)
    app.router.add_post(_p("/v1/rerank"), create_rerank)
    app.router.add_get(_p("/v1/models"), list_models)
    app.router.add_get(_p("/v1/models/{model}"), get_model)
    app.router.add_get(
        _p("/v1/chat/completions/{completion_id}"), retrieve_stored_completion
    )
    app.router.add_post(
        _p("/v1/chat/completions/{completion_id}"), update_stored_completion
    )
    app.router.add_delete(
        _p("/v1/chat/completions/{completion_id}"), delete_stored_completion
    )
    app.router.add_get(
        _p("/v1/chat/completions/{completion_id}/messages"),
        list_stored_completion_messages,
    )


def _register_openai_files_routes(app: aiohttp.web.Application) -> None:
    app.router.add_post(_p("/v1/files"), upload_file)
    app.router.add_get(_p("/v1/files"), list_files)
    app.router.add_get(_p("/v1/files/{file_id}"), retrieve_file)
    app.router.add_delete(_p("/v1/files/{file_id}"), delete_file)
    app.router.add_get(_p("/v1/files/{file_id}/content"), retrieve_file_content)


def _register_openai_beta_routes(app: aiohttp.web.Application) -> None:
    app.router.add_post(_p("/v1/fine_tuning/jobs"), create_fine_tuning_job)
    app.router.add_get(_p("/v1/fine_tuning/jobs"), list_fine_tuning_jobs)
    app.router.add_get(
        _p("/v1/fine_tuning/jobs/{fine_tuning_job_id}"), retrieve_fine_tuning_job
    )
    app.router.add_post(
        _p("/v1/fine_tuning/jobs/{fine_tuning_job_id}/cancel"), cancel_fine_tuning_job
    )
    app.router.add_get(
        _p("/v1/fine_tuning/jobs/{fine_tuning_job_id}/events"), list_fine_tuning_events
    )
    app.router.add_post(_p("/v1/batches"), create_batch)
    app.router.add_get(_p("/v1/batches"), list_batches)
    app.router.add_get(_p("/v1/batches/{batch_id}"), retrieve_batch)
    app.router.add_post(_p("/v1/batches/{batch_id}/cancel"), cancel_batch)
    app.router.add_post(_p("/v1/assistants"), create_assistant)
    app.router.add_get(_p("/v1/assistants"), list_assistants)
    app.router.add_get(_p("/v1/assistants/{assistant_id}"), retrieve_assistant)
    app.router.add_post(_p("/v1/assistants/{assistant_id}"), modify_assistant)
    app.router.add_delete(_p("/v1/assistants/{assistant_id}"), delete_assistant)
    app.router.add_post(_p("/v1/threads"), create_thread)
    app.router.add_get(_p("/v1/threads/{thread_id}"), retrieve_thread)
    app.router.add_post(_p("/v1/threads/{thread_id}"), modify_thread)
    app.router.add_delete(_p("/v1/threads/{thread_id}"), delete_thread)
    app.router.add_post(_p("/v1/threads/{thread_id}/messages"), create_thread_message)
    app.router.add_get(_p("/v1/threads/{thread_id}/messages"), list_thread_messages)
    app.router.add_post(_p("/v1/threads/{thread_id}/runs"), create_run)
    app.router.add_get(_p("/v1/threads/{thread_id}/runs"), list_runs)
    app.router.add_get(_p("/v1/threads/{thread_id}/runs/{run_id}"), retrieve_run)
    app.router.add_post(_p("/v1/threads/{thread_id}/runs/{run_id}/cancel"), cancel_run)
    app.router.add_post(
        _p("/v1/threads/{thread_id}/runs/{run_id}/submit_tool_outputs"), submit_tool_outputs
    )
    app.router.add_post(_p("/v1/vector_stores"), create_vector_store)
    app.router.add_get(_p("/v1/vector_stores"), list_vector_stores)
    app.router.add_get(_p("/v1/vector_stores/{vector_store_id}"), retrieve_vector_store)
    app.router.add_delete(_p("/v1/vector_stores/{vector_store_id}"), delete_vector_store)
    app.router.add_post(
        _p("/v1/vector_stores/{vector_store_id}/files"), create_vector_store_file
    )
    app.router.add_get(
        _p("/v1/vector_stores/{vector_store_id}/files"), list_vector_store_files
    )
    app.router.add_post(_p("/v1/uploads"), create_upload)
    app.router.add_post(_p("/v1/uploads/{upload_id}/parts"), add_upload_part)
    app.router.add_post(_p("/v1/uploads/{upload_id}/complete"), complete_upload)
    app.router.add_post(_p("/v1/uploads/{upload_id}/cancel"), cancel_upload)


def setup_routes(app: aiohttp.web.Application) -> None:
    """注册所有 OpenAI 兼容路由。"""
    _register_openai_core_routes(app)
    _register_openai_files_routes(app)
    _register_openai_beta_routes(app)
    register_catalog_routes(app)
