from __future__ import annotations

"""Anthropic 流式 SSE 事件写入与消息生成。"""

import asyncio
from typing import Any, Dict, List, Optional

import aiohttp.web

from src.core.server import REGISTRY_KEY
from src.core.utils.compat.tools import parse_fncall_xml
from src.core.utils.errors import NoCandidateError, ProviderError
from src.foundation.config.resolve import resolve_model
from src.foundation.logger import get_logger
from src.routes.anthropic.convert import _build_dispatch_kwargs, _mid
from src.routes.anthropic.streaming.stream_events import TextDeltaState, write_event
from src.routes.anthropic.streaming.stream_tools import emit_tool_use_blocks

logger = get_logger(__name__)

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


async def _emit_stream_error(
    resp: aiohttp.web.StreamResponse, error_type: str, message: str
) -> None:
    """输出流式错误事件。"""
    await write_event(
        resp,
        "error",
        {"type": "error", "error": {"type": error_type, "message": message}},
    )


async def _init_stream_blocks(
    request: aiohttp.web.Request,
    body: Dict[str, Any],
    msgs: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]],
    thinking: bool,
) -> tuple:
    """准备响应并输出 message_start 与首个 content block，返回后续处理所需状态。

    Returns:
        (resp, text_state, text_block_idx, effective_thinking) 元组。
    """
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
    """运行 gateway 消费循环并捕获流式错误，返回 None 表示已提前结束响应。"""
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
    """处理流消费结果，收尾 thinking/text block 并输出 tool_use/message_delta/message_stop。"""
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


async def _stream_messages(
    request: aiohttp.web.Request,
    body: Dict[str, Any],
    msgs: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]],
    thinking: bool,
) -> aiohttp.web.StreamResponse:
    """Anthropic 流式消息生成核心实现。

    按 Anthropic SSE 规范输出事件序列：
    message_start → content_block_start → content_block_delta(s)
    → content_block_stop → [tool_use blocks] → message_delta → message_stop

    Args:
        request: 请求对象。
        body: 已解析的请求体。
        msgs: 已转换的 OpenAI 格式消息列表。
        tools: 已转换的 OpenAI 格式工具列表。
        thinking: 是否开启 thinking 模式。

    Returns:
        StreamResponse 实例。
    """
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
