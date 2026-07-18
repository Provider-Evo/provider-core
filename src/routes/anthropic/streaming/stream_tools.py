from __future__ import annotations

"""Anthropic 流式 tool_use content block 输出。"""

import json
from typing import Any, Dict, List

import aiohttp.web
from src.routes.anthropic.convert import _openai_tc_to_anth
from src.routes.anthropic.streaming.stream_events import write_event

_JSON_CHUNK = 20


async def _emit_single_tool_use_block(
    resp: aiohttp.web.StreamResponse,
    tc: Dict[str, Any],
    ti: int,
) -> None:
    """输出单个 tool_use content block（start / 分块 delta / stop）。"""
    anth_tc = _openai_tc_to_anth(tc)
    args_raw = tc.get("function", {}).get("arguments", "{}")
    if isinstance(args_raw, dict):
        args_str = json.dumps(args_raw, ensure_ascii=False)
    else:
        args_str = str(args_raw)

    await write_event(
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
    for j_off in range(0, max(1, len(args_str)), _JSON_CHUNK):
        j_chunk = args_str[j_off: j_off + _JSON_CHUNK]
        await write_event(
            resp,
            "content_block_delta",
            {
                "type": "content_block_delta",
                "index": ti,
                "delta": {
                    "type": "input_json_delta",
                    "partial_json": j_chunk,
                },
            },
        )
    await write_event(
        resp,
        "content_block_stop",
        {"type": "content_block_stop", "index": ti},
    )


async def emit_tool_use_blocks(
    resp: aiohttp.web.StreamResponse,
    tool_calls_data: List[Dict[str, Any]],
    next_block_idx: int,
) -> None:
    """按 Anthropic 规范逐个输出 tool_use content block。

    Args:
        resp: 流式响应对象。
        tool_calls_data: OpenAI 格式的工具调用列表。
        next_block_idx: 首个 tool_use block 的起始索引。
    """
    for i, tc in enumerate(tool_calls_data):
        await _emit_single_tool_use_block(resp, tc, next_block_idx + i)
