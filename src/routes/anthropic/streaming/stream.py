from __future__ import annotations

"""Anthropic 流式 SSE 事件写入与消息生成。"""

from typing import Any, Dict, List, Optional, Tuple

import aiohttp.web

from src.core.server import REGISTRY_KEY
from src.core.utils.compat.tools import parse_fncall_xml
from src.foundation.config.resolve import resolve_model
from src.routes.anthropic.convert import _build_dispatch_kwargs, _mid
from src.routes.anthropic.streaming.stream_events import TextDeltaState, write_event

_THINKING_CHUNK = 20


async def _prepare_response(
    request: aiohttp.web.Request,
) -> aiohttp.web.StreamResponse:
    """创建并准备流式响应。"""
    resp = aiohttp.web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
    await resp.prepare(request)
    return resp


async def _emit_message_start(
    resp: aiohttp.web.StreamResponse, mid: str, mdl: str, pt: int
) -> None:
    """输出 message_start 与开场 ping 事件。"""
    await write_event(
        resp,
        "message_start",
        {
            "type": "message_start",
            "message": {
                "id": mid,
                "type": "message",
                "role": "assistant",
                "content": [],
                "model": mdl,
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": pt, "output_tokens": 1},
            },
        },
    )
    await write_event(resp, "ping", {"type": "ping"})


async def _emit_block_start(
    resp: aiohttp.web.StreamResponse, index: int, block: Dict[str, Any]
) -> None:
    """输出 content_block_start 事件。"""
    await write_event(
        resp,
        "content_block_start",
        {"type": "content_block_start", "index": index, "content_block": block},
    )


async def _emit_thinking_delta(
    resp: aiohttp.web.StreamResponse, thinking_text: str
) -> None:
    """按固定步长分块输出 thinking_delta。"""
    for t_off in range(0, max(1, len(thinking_text)), _THINKING_CHUNK):
        t_chunk = thinking_text[t_off : t_off + _THINKING_CHUNK]
        await write_event(
            resp,
            "content_block_delta",
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "thinking_delta", "thinking": t_chunk},
            },
        )


async def _handle_gateway_dict_chunk(
    resp: aiohttp.web.StreamResponse,
    ch: Dict[str, Any],
    text_state: TextDeltaState,
    effective_thinking: bool,
    tool_calls_data: List[Dict[str, Any]],
    usage_d: Optional[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    if "_meta" in ch:
        platform_id = ch["_meta"].get("platform", "")
        if platform_id:
            text_state.platform_id = platform_id
            resp._platform = platform_id
        return tool_calls_data, usage_d
    if "thinking" in ch and effective_thinking:
        await _emit_thinking_delta(resp, ch["thinking"])
        return tool_calls_data, usage_d
    if "tool_calls" in ch:
        return ch["tool_calls"], usage_d
    if "usage" in ch:
        return tool_calls_data, ch["usage"]
    return tool_calls_data, usage_d


async def _consume_gateway(
    request: aiohttp.web.Request,
    resp: aiohttp.web.StreamResponse,
    body: Dict[str, Any],
    msgs: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]],
    text_state: TextDeltaState,
    effective_thinking: bool,
    buffered_text_chunks: List[str],
) -> Dict[str, Any]:
    """消费 gateway.dispatch 流并写出增量事件。

    Returns:
        包含 tool_calls_data、usage_d、output_tokens 的结果字典。
    """
    from src.core import gateway

    tool_calls_data: List[Dict[str, Any]] = []
    usage_d: Optional[Dict[str, Any]] = None
    output_tokens = 0

    async for ch in gateway.dispatch(
        **_build_dispatch_kwargs(body, msgs, True, request.app[REGISTRY_KEY], tools)
    ):
        if isinstance(ch, str):
            output_tokens += 1
            if effective_thinking:
                buffered_text_chunks.append(ch)
            else:
                await text_state.emit(ch)
            continue
        if isinstance(ch, dict):
            tool_calls_data, usage_d = await _handle_gateway_dict_chunk(
                resp,
                ch,
                text_state,
                effective_thinking,
                tool_calls_data,
                usage_d,
            )

    return {
        "tool_calls_data": tool_calls_data,
        "usage_d": usage_d,
        "output_tokens": output_tokens,
    }


async def _finalize_thinking_block(
    resp: aiohttp.web.StreamResponse,
    text_state: TextDeltaState,
    effective_thinking: bool,
    buffered_text_chunks: List[str],
) -> None:
    """结束 thinking block 并开启文本 block，回放缓冲文本。"""
    if not effective_thinking:
        return
    await write_event(
        resp,
        "content_block_stop",
        {"type": "content_block_stop", "index": 0},
    )
    await _emit_block_start(
        resp, text_state.text_block_idx, {"type": "text", "text": ""}
    )
    for text_chunk in buffered_text_chunks:
        await text_state.emit(text_chunk)


async def _finalize_text_block(
    resp: aiohttp.web.StreamResponse,
    text_state: TextDeltaState,
    tool_calls_data: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """输出文本缓冲剩余内容并关闭文本 block，解析未决的 fncall。

    Returns:
        最终的 tool_calls_data（若之前为空且检测到 fncall，则由此解析得到）。
    """
    if text_state.text_buffer and not text_state.in_fncall:
        await text_state._write_text_delta(text_state.text_buffer)

    if text_state.in_fncall and text_state.fncall_buffer and not tool_calls_data:
        tool_calls_data = parse_fncall_xml(text_state.fncall_buffer, tools)

    await write_event(
        resp,
        "content_block_stop",
        {"type": "content_block_stop", "index": text_state.text_block_idx},
    )
    return tool_calls_data


async def _emit_message_delta_and_stop(
    resp: aiohttp.web.StreamResponse,
    tool_calls_data: List[Dict[str, Any]],
    usage_d: Optional[Dict[str, Any]],
    output_tokens: int,
) -> None:
    """输出 message_delta（stop_reason + usage）与 message_stop。"""
    stop_reason = "tool_use" if tool_calls_data else "end_turn"
    ou = output_tokens
    if usage_d:
        ou = (
            usage_d.get("completion_tokens")
            or usage_d.get("output_tokens")
            or output_tokens
        )

    await write_event(
        resp,
        "message_delta",
        {
            "type": "message_delta",
            "delta": {"stop_reason": stop_reason, "stop_sequence": None},
            "usage": {"output_tokens": ou},
        },
    )
    await write_event(resp, "message_stop", {"type": "message_stop"})


async def _init_stream_blocks(
    request: aiohttp.web.Request,
    body: Dict[str, Any],
    msgs: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]],
    thinking: bool,
) -> tuple:
    """准备响应并输出 message_start 与首个 content block，返回后续处理所需状态。"""
    mid = _mid()
    mdl = resolve_model(body.get("model", ""), "anthropic")
    pt = sum(len(str(m.get("content", ""))) // 3 for m in msgs)

    resp = await _prepare_response(request)
    await _emit_message_start(resp, mid, mdl, pt)

    block_idx = 0
    effective_thinking = thinking and not tools
    if effective_thinking:
        await _emit_block_start(resp, 0, {"type": "thinking", "thinking": ""})
        block_idx = 1

    text_block_idx = block_idx
    if not effective_thinking:
        await _emit_block_start(resp, text_block_idx, {"type": "text", "text": ""})

    text_state = TextDeltaState(resp, request, text_block_idx)
    return resp, text_state, text_block_idx, effective_thinking


async def _stream_messages(
    request: aiohttp.web.Request,
    body: Dict[str, Any],
    msgs: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]],
    thinking: bool,
) -> aiohttp.web.StreamResponse:
    """Anthropic 流式消息生成（委托 stream_orchestrate）。"""
    from src.routes.anthropic.streaming.stream_orchestrate import stream_messages

    return await stream_messages(request, body, msgs, tools, thinking)
