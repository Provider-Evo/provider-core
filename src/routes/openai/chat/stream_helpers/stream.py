# -*- coding: utf-8 -*-
from __future__ import annotations

"""OpenAI Chat Completions — 流式 SSE 处理。"""

import asyncio
import time
from typing import Any, Dict

import aiohttp.web

from src.foundation.config.resolve import resolve_model
from src.foundation.logger import get_logger
from src.routes.openai.chat.helpers import (
    _cid,
    _extract_upload_files,
    _normalize_messages,
)
from src.routes.openai.chat.stream_helpers.sse_processor import SSEStreamProcessor
from src.routes.openai.chat.stream_helpers.stream_events import build_stream_state
from src.routes.openai.chat.stream_helpers.stream_helpers import (
    _SSE_HEADERS,
    _build_dispatch_kwargs,
    _handle_dispatch_exception,
)

__all__ = ["stream_chat"]

logger = get_logger(__name__)


async def _run_stream_dispatch(
    state: Any,
    dispatch_kwargs: Dict[str, Any],
    processor: SSEStreamProcessor,
    resp: aiohttp.web.StreamResponse,
) -> aiohttp.web.StreamResponse | None:
    from src.core import gateway

    try:
        async for ch in gateway.dispatch(**dispatch_kwargs):
            processor.stop()
            if isinstance(ch, str):
                await state.process_str_chunk(ch)
            elif isinstance(ch, dict):
                await state.process_dict_chunk(ch)
    except asyncio.CancelledError:
        return resp
    except ConnectionResetError:
        return resp
    except Exception as e:
        return await _handle_dispatch_exception(e, resp)
    return None


async def _await_cancelled(task: asyncio.Task) -> None:
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def _stream_chat_setup(body: Dict[str, Any], thinking_flavor: str):
    mdl = resolve_model(body.get("model", ""), "openai")
    extra = body.get("extra_body") or body.get("extra") or {}
    from src.routes.shared.thinking import (
        resolve_include_thinking_in_history,
        resolve_thinking_config,
    )

    thinking_cfg = resolve_thinking_config(body, extra=extra, flavor=thinking_flavor)  # type: ignore[arg-type]
    include = resolve_include_thinking_in_history(
        body, extra=extra, thinking_cfg=thinking_cfg
    )
    messages = _normalize_messages(
        body.get("messages", []),
        include_thinking_in_history=include,
    )
    return mdl, extra, messages, body.get("tools"), _extract_upload_files(messages), body.get("protocol", "")


async def stream_chat(
    request: aiohttp.web.Request,
    body: Dict[str, Any],
    *,
    thinking_flavor: str = "openai",
) -> aiohttp.web.StreamResponse:
    """流式聊天补全。"""
    cid = _cid()
    ct = int(time.time())
    mdl, extra, messages, tools_raw, upload_files, proto_override = _stream_chat_setup(
        body, thinking_flavor
    )

    resp = aiohttp.web.StreamResponse(status=200, headers=_SSE_HEADERS)
    await resp.prepare(request)

    state = await build_stream_state(request, resp, cid, ct, mdl, tools_raw)
    state.proto_override = proto_override

    dispatch_kwargs = _build_dispatch_kwargs(
        request,
        body,
        messages,
        mdl,
        tools_raw,
        extra,
        upload_files,
        proto_override,
        thinking_flavor=thinking_flavor,
    )

    processor = SSEStreamProcessor()
    comment_task = asyncio.create_task(processor.run_initial_comments(resp))

    early = await _run_stream_dispatch(state, dispatch_kwargs, processor, resp)
    processor.stop()
    # SSE 心跳注释任务与主流式互斥；须 cancel 并 await，否则 run_initial_comments 在后台空转
    await _await_cancelled(comment_task)
    if early is not None:
        return early

    await state.finalize()
    return resp
