# -*- coding: utf-8 -*-
from __future__ import annotations

"""OpenAI Chat Completions — 流式 SSE 处理。"""

import asyncio
import time
from typing import Any, Dict

import aiohttp.web

from src.foundation.config.resolve import resolve_model
from src.foundation.logger import get_logger
from src.routes.openai.chat.helpers import _cid, _extract_upload_files, _normalize_messages
from src.routes.openai.chat.stream_helpers.stream_events import build_stream_state
from src.routes.openai.chat.stream_helpers.stream_helpers import _SSE_HEADERS, _build_dispatch_kwargs, _handle_dispatch_exception

__all__ = ["stream_chat"]

logger = get_logger(__name__)


async def stream_chat(
    request: aiohttp.web.Request,
    body: Dict[str, Any],
) -> aiohttp.web.StreamResponse:
    """流式聊天补全。"""
    from src.core import gateway

    cid = _cid()
    ct = int(time.time())
    mdl = resolve_model(body.get("model", ""), "openai")
    messages = _normalize_messages(body.get("messages", []))
    tools_raw = body.get("tools")
    extra = body.get("extra_body") or body.get("extra") or {}
    upload_files = _extract_upload_files(messages)
    proto_override = body.get("protocol", "")

    resp = aiohttp.web.StreamResponse(status=200, headers=_SSE_HEADERS)
    await resp.prepare(request)

    state = await build_stream_state(request, resp, cid, ct, mdl, tools_raw)
    state.proto_override = proto_override

    dispatch_kwargs = _build_dispatch_kwargs(
        request, body, messages, mdl, tools_raw, extra, upload_files, proto_override,
    )

    try:
        async for ch in gateway.dispatch(**dispatch_kwargs):
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

    await state.finalize()
    return resp
