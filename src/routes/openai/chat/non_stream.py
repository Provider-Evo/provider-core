
import time
from typing import Any, Dict, List, Optional

import aiohttp.web

from src.core.server import REGISTRY_KEY
from src.core.server import clean_fncall as _clean_fncall
from src.entropy.adapters.from_openai import from_openai_chat_body
from src.entropy.core.turn import collect_turn
from src.foundation.config.resolve import resolve_model
from src.foundation.logger import get_logger
from src.routes.openai.chat.helpers import (
    _cid,
    _extract_upload_files,
    _normalize_messages,
    _sl,
)

__all__ = [
    "build_chat_completion_payload",
    "collect_nonstream_chat",
    "fallback_parse_tool_calls",
]

logger = get_logger(__name__)


async def collect_nonstream_chat(
    request: aiohttp.web.Request,
    body: Dict[str, Any],
    messages: List[Dict[str, Any]],
    mdl: str,
    *,
    thinking_flavor: str = "openai",
) -> tuple[List[str], List[str], List[Dict], Optional[Dict], str]:
    """非流式补全：经 execute_turn 收集输出。"""
    turn_req = from_openai_chat_body(body, flavor=thinking_flavor)
    turn_req.model = mdl
    turn_req.stream = False
    turn_resp = await collect_turn(turn_req, request.app[REGISTRY_KEY])
    cp = [turn_resp.raw_text] if turn_resp.raw_text else []
    tp = [
        b.thinking
        for b in turn_resp.output
        if b.type == "thinking" and b.thinking
    ]
    return cp, tp, turn_resp.tool_calls, turn_resp.usage, turn_resp.platform_id


def fallback_parse_tool_calls(
    content: str,
    tcs: List[Dict],
    platform_id: str,
    proto_override: str,
    tools: Any,
) -> tuple[str, List[Dict]]:
    """非流式兜底：从完整文本中解析 tool_calls。"""
    if tcs or not content:
        return content, tcs
    try:
        from src.core.fncall.reg import get_protocol

        proto = get_protocol(platform_id=platform_id)
        cleaned, extracted = proto.parse(content, tools)
        if extracted:
            return cleaned, extracted
    except Exception as exc:
        logger.debug("非流式兜底 fncall 解析失败: %s", exc)
    return content, tcs


def build_chat_completion_payload(
    mdl: str,
    content: str,
    tp: List[str],
    tcs: List[Dict],
    usage_d: Optional[Dict],
) -> Dict[str, Any]:
    """组装非流式 chat.completion JSON 载荷。"""
    u = usage_d or {
        "prompt_tokens": 0,
        "completion_tokens": len(content) // 3 if content else 0,
        "total_tokens": len(content) // 3 if content else 0,
    }
    msg: Dict[str, Any] = {"role": "assistant"}
    if content:
        msg["content"] = content
    if tp:
        reasoning_text = "".join(tp)
        msg["reasoning"] = reasoning_text
        msg["reasoning_details"] = [
            {
                "type": "reasoning.text",
                "text": reasoning_text,
                "format": "unknown",
                "index": 0,
            }
        ]
    if tcs:
        msg["tool_calls"] = tcs
    return {
        "id": _cid(),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": mdl,
        "choices": [
            {
                "index": 0,
                "message": msg,
                "finish_reason": "tool_calls" if tcs else "stop",
            }
        ],
        "usage": u,
    }
