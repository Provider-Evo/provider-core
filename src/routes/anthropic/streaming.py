from __future__ import annotations

"""Anthropic 流式 SSE 事件写入与消息生成。"""

import asyncio
import json
from typing import Any, Dict, List, Optional

import aiohttp.web
from src.core.config.resolver import resolve_model
from src.core.errors import NoCandidateError, ProviderError
from src.core.server import REGISTRY_KEY, safe_flush as _safe_flush
from src.core.utils.compat.tools import parse_fncall_xml
from src.foundation.logger import get_logger

from src.routes.anthropic.convert import (
    _build_dispatch_kwargs,
    _mid,
    _openai_tc_to_anth,
)

logger = get_logger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# 流式写入工具
# ═══════════════════════════════════════════════════════════════════════════


async def _write_event(
    resp: aiohttp.web.StreamResponse,
    event: str,
    data: Dict[str, Any],
) -> None:
    """向流式响应写入一个 Anthropic SSE 事件。

    Args:
        resp: 流式响应对象。
        event: 事件名称。
        data: 事件数据字典。
    """
    line = "event: {}\ndata: {}\n\n".format(
        event, json.dumps(data, ensure_ascii=False)
    )
    try:
        await resp.write(line.encode("utf-8"))
    except (ConnectionError, OSError) as exc:
        logger.warning("SSE 事件写入失败: %s", exc)


# ═══════════════════════════════════════════════════════════════════════════
# 流式消息生成
# ═══════════════════════════════════════════════════════════════════════════


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
    from src.core import gateway

    mid = _mid()
    mdl = resolve_model(body.get("model", ""), "anthropic")
    pt = sum(len(str(m.get("content", ""))) // 3 for m in msgs)

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

    # message_start
    await _write_event(
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

    # ping（Anthropic 标准流开头）
    await _write_event(resp, "ping", {"type": "ping"})

    # content block 索引管理
    block_idx = 0

    # thinking block（若开启且无工具调用，避免冲突）
    effective_thinking = thinking and not tools
    if effective_thinking:
        await _write_event(
            resp,
            "content_block_start",
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "thinking", "thinking": ""},
            },
        )
        block_idx = 1

    # 主文本 block 索引；effective_thinking=True 时延迟开启，确保顺序正确
    text_block_idx = block_idx
    if not effective_thinking:
        await _write_event(
            resp,
            "content_block_start",
            {
                "type": "content_block_start",
                "index": text_block_idx,
                "content_block": {"type": "text", "text": ""},
            },
        )

    # 状态变量
    platform_id = ""        # 从 _meta 获取的平台 ID，用于协议感知
    text_buffer = ""       # 普通文本缓冲（检测 fncall 前缀）
    fncall_buffer = ""     # fncall XML 累积缓冲
    in_fncall = False       # 是否已进入 fncall 累积模式
    buffered_text_chunks: List[str] = []
    tool_calls_data: List[Dict[str, Any]] = []
    usage_d: Optional[Dict[str, Any]] = None
    output_tokens = 0

    async def _emit_text_delta_chunk(chunk: str) -> None:
        """处理并输出单个文本分片。"""
        nonlocal text_buffer, fncall_buffer, in_fncall, platform_id

        if in_fncall:
            fncall_buffer += chunk
            return

        text_buffer += chunk

        # 协议感知的标签检测
        from src.core.fncall.registry import get_protocol
        proto = get_protocol(platform_id=platform_id)
        trigger_tags = proto.get_trigger_tags()

        tag_idx = -1
        for tag in trigger_tags:
            idx = text_buffer.find(tag)
            if idx != -1 and (tag_idx == -1 or idx < tag_idx):
                tag_idx = idx
        if tag_idx != -1:
            safe_part = text_buffer[:tag_idx]
            if safe_part:
                _log_chunks = request.get("_req_log_chunks")
                if _log_chunks is not None:
                    _log_chunks.append(safe_part)
                await _write_event(
                    resp,
                    "content_block_delta",
                    {
                        "type": "content_block_delta",
                        "index": text_block_idx,
                        "delta": {
                            "type": "text_delta",
                            "text": safe_part,
                        },
                    },
                )
            fncall_buffer = text_buffer[tag_idx:]
            text_buffer = ""
            in_fncall = True
            return

        # 提取安全可输出部分
        safe_part, text_buffer = _safe_flush(text_buffer, platform_id=platform_id)
        if safe_part:
            _log_chunks = request.get("_req_log_chunks")
            if _log_chunks is not None:
                _log_chunks.append(safe_part)
            await _write_event(
                resp,
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": text_block_idx,
                    "delta": {
                        "type": "text_delta",
                        "text": safe_part,
                    },
                },
            )

    try:
        async for ch in gateway.dispatch(
            **_build_dispatch_kwargs(body, msgs, True, request.app[REGISTRY_KEY], tools)
        ):
            if isinstance(ch, str):
                output_tokens += 1
                if effective_thinking:
                    buffered_text_chunks.append(ch)
                else:
                    await _emit_text_delta_chunk(ch)

            elif isinstance(ch, dict):
                if "_meta" in ch:
                    platform_id = ch["_meta"].get("platform", "")
                    if platform_id:
                        resp._platform = platform_id
                elif "thinking" in ch and effective_thinking:
                    thinking_text = ch["thinking"]
                    # 分块输出 thinking_delta，固定步长 20 字符
                    _THINKING_CHUNK = 20
                    for _t_off in range(
                        0, max(1, len(thinking_text)), _THINKING_CHUNK
                    ):
                        _t_chunk = thinking_text[_t_off: _t_off + _THINKING_CHUNK]
                        await _write_event(
                            resp,
                            "content_block_delta",
                            {
                                "type": "content_block_delta",
                                "index": 0,
                                "delta": {
                                    "type": "thinking_delta",
                                    "thinking": _t_chunk,
                                },
                            },
                        )
                elif "tool_calls" in ch:
                    tool_calls_data = ch["tool_calls"]
                elif "usage" in ch:
                    usage_d = ch["usage"]

    except asyncio.CancelledError:
        return resp
    except ConnectionResetError:
        return resp
    except NoCandidateError as exc:
        logger.warning("Anthropic 流式请求无候选项: %s", exc)
        await _write_event(
            resp,
            "error",
            {
                "type": "error",
                "error": {"type": "overloaded_error", "message": str(exc)},
            },
        )
        return resp
    except ProviderError as exc:
        logger.warning("Anthropic 流式 Provider 错误: %s", exc)
        await _write_event(
            resp,
            "error",
            {
                "type": "error",
                "error": {"type": "api_error", "message": str(exc)},
            },
        )
        return resp
    except Exception as exc:
        logger.error("Anthropic 流式错误: %s", exc, exc_info=True)
        await _write_event(
            resp,
            "error",
            {
                "type": "error",
                "error": {"type": "server_error", "message": str(exc)},
            },
        )
        return resp

    # effective_thinking 模式：先完整结束 thinking，再开始 text
    if effective_thinking:
        await _write_event(
            resp,
            "content_block_stop",
            {"type": "content_block_stop", "index": 0},
        )
        await _write_event(
            resp,
            "content_block_start",
            {
                "type": "content_block_start",
                "index": text_block_idx,
                "content_block": {"type": "text", "text": ""},
            },
        )
        for _text_chunk in buffered_text_chunks:
            await _emit_text_delta_chunk(_text_chunk)

    # 输出文本缓冲剩余
    if text_buffer and not in_fncall:
        await _write_event(
            resp,
            "content_block_delta",
            {
                "type": "content_block_delta",
                "index": text_block_idx,
                "delta": {"type": "text_delta", "text": text_buffer},
            },
        )

    # 解析 fncall buffer（如果尚未通过 tool_calls 获得）
    if in_fncall and fncall_buffer and not tool_calls_data:
        tool_calls_data = parse_fncall_xml(fncall_buffer, tools)

    # content_block_stop：文本 block
    await _write_event(
        resp,
        "content_block_stop",
        {"type": "content_block_stop", "index": text_block_idx},
    )

    # tool_use blocks（按 Anthropic 规范逐个输出）
    next_block_idx = text_block_idx + 1
    for i, tc in enumerate(tool_calls_data):
        ti = next_block_idx + i
        anth_tc = _openai_tc_to_anth(tc)
        # arguments 字符串（用于 input_json_delta）
        args_raw = tc.get("function", {}).get("arguments", "{}")
        if isinstance(args_raw, dict):
            args_str = json.dumps(args_raw, ensure_ascii=False)
        else:
            args_str = str(args_raw)

        await _write_event(
            resp,
            "content_block_start",
            {
                "type": "content_block_start",
                "index": ti,
                "content_block": {
                    "type": "tool_use",
                    "id": anth_tc["id"],
                    "name": anth_tc["name"],
                    "input": {},
                },
            },
        )
        # 按固定步长 20 字符分块输出 input_json_delta
        _JSON_CHUNK = 20
        for _j_off in range(0, max(1, len(args_str)), _JSON_CHUNK):
            _j_chunk = args_str[_j_off: _j_off + _JSON_CHUNK]
            await _write_event(
                resp,
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": ti,
                    "delta": {
                        "type": "input_json_delta",
                        "partial_json": _j_chunk,
                    },
                },
            )
        await _write_event(
            resp,
            "content_block_stop",
            {"type": "content_block_stop", "index": ti},
        )

    # message_delta（stop_reason + usage）
    stop_reason = "tool_use" if tool_calls_data else "end_turn"
    ou = output_tokens
    if usage_d:
        ou = (
            usage_d.get("completion_tokens")
            or usage_d.get("output_tokens")
            or output_tokens
        )

    await _write_event(
        resp,
        "message_delta",
        {
            "type": "message_delta",
            "delta": {
                "stop_reason": stop_reason,
                "stop_sequence": None,
            },
            "usage": {"output_tokens": ou},
        },
    )

    # message_stop
    await _write_event(resp, "message_stop", {"type": "message_stop"})

    return resp
