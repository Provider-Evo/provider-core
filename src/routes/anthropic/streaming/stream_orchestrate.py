"""Anthropic 流式消息编排：gateway 消费与收尾。"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import aiohttp.web

from src.core.utils.errors import NoCandidateError, ProviderError
from src.foundation.logger import get_logger
from src.routes.anthropic.streaming.stream_events import TextDeltaState, write_event
from src.routes.anthropic.streaming.stream_tools import emit_tool_use_blocks

logger = get_logger(__name__)


async def _emit_stream_error(
    resp: aiohttp.web.StreamResponse, error_type: str, message: str
) -> None:
    await write_event(
        resp,
        "error",
        {"type": "error", "error": {"type": error_type, "message": message}},
    )


async def _run_stream_gateway(
    request: aiohttp.web.Request,
    resp: aiohttp.web.StreamResponse,
    body: Dict[str, Any],
    msgs: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]],
    text_state: TextDeltaState,
    effective_thinking: bool,
    buffered_text_chunks: List[str],
) -> Optional[Dict[str, Any]]:
    from src.routes.anthropic.streaming.stream import _consume_gateway

    try:
        return await _consume_gateway(
            request,
            resp,
            body,
            msgs,
            tools,
            text_state,
            effective_thinking,
            buffered_text_chunks,
        )
    except asyncio.CancelledError:
        return None
    except ConnectionResetError:
        return None
    except NoCandidateError as exc:
        logger.warning("Anthropic 流式请求无候选项: %s", exc)
        await _emit_stream_error(resp, "overloaded_error", str(exc))
        return None
    except ProviderError as exc:
        logger.warning("Anthropic 流式 Provider 错误: %s", exc)
        await _emit_stream_error(resp, "api_error", str(exc))
        return None
    except Exception as exc:
        logger.error("Anthropic 流式错误: %s", exc, exc_info=True)
        await _emit_stream_error(resp, "server_error", str(exc))
        return None


async def _finalize_stream_result(
    resp: aiohttp.web.StreamResponse,
    text_state: TextDeltaState,
    text_block_idx: int,
    tools: Optional[List[Dict[str, Any]]],
    effective_thinking: bool,
    buffered_text_chunks: List[str],
    result: Dict[str, Any],
) -> None:
    from src.routes.anthropic.streaming.stream import (
        _emit_message_delta_and_stop,
        _finalize_text_block,
        _finalize_thinking_block,
    )

    tool_calls_data = result["tool_calls_data"]
    usage_d = result["usage_d"]
    output_tokens = result["output_tokens"]

    await _finalize_thinking_block(
        resp, text_state, effective_thinking, buffered_text_chunks
    )
    tool_calls_data = await _finalize_text_block(
        resp, text_state, tool_calls_data, tools
    )

    next_block_idx = text_block_idx + 1
    await emit_tool_use_blocks(resp, tool_calls_data, next_block_idx)

    await _emit_message_delta_and_stop(resp, tool_calls_data, usage_d, output_tokens)


async def stream_messages(
    request: aiohttp.web.Request,
    body: Dict[str, Any],
    msgs: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]],
    thinking: bool,
) -> aiohttp.web.StreamResponse:
    from src.routes.anthropic.streaming.stream import _init_stream_blocks

    resp, text_state, text_block_idx, effective_thinking = await _init_stream_blocks(
        request, body, msgs, tools, thinking
    )
    buffered_text_chunks: List[str] = []

    result = await _run_stream_gateway(
        request,
        resp,
        body,
        msgs,
        tools,
        text_state,
        effective_thinking,
        buffered_text_chunks,
    )
    if result is None:
        return resp

    await _finalize_stream_result(
        resp,
        text_state,
        text_block_idx,
        tools,
        effective_thinking,
        buffered_text_chunks,
        result,
    )

    return resp
