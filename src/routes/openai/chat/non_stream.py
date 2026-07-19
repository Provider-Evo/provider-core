"""nonstream 模块 — HTTP 入口路由。

职责：
    作为 Provider-Evo 项目标准模块，提供 nonstream 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""

import time
from typing import Any, Dict, List, Optional

import aiohttp.web

from src.core.server import REGISTRY_KEY
from src.core.server import clean_fncall as _clean_fncall
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


def _collect_nonstream_dict_chunk(
    ch: Dict[str, Any],
    tp: List[str],
    tcs: List[Dict],
    usage_d: Optional[Dict],
    platform_id: str,
) -> tuple[List[Dict], Optional[Dict], str]:
    if "_meta" in ch:
        return tcs, usage_d, ch["_meta"].get("platform", "")
    if "thinking" in ch:
        tp.append(ch["thinking"])
    elif "tool_calls" in ch:
        tcs = ch["tool_calls"]
    elif "usage" in ch:
        usage_d = ch["usage"]
    return tcs, usage_d, platform_id


async def collect_nonstream_chat(
    request: aiohttp.web.Request,
    body: Dict[str, Any],
    messages: List[Dict[str, Any]],
    mdl: str,
) -> tuple[List[str], List[str], List[Dict], Optional[Dict], str]:
    """非流式补全：调用网关并聚合文本、thinking、tool_calls。"""
    from src.core import gateway

    extra = body.get("extra_body") or body.get("extra") or {}
    cp: List[str] = []
    tp: List[str] = []
    tcs: List[Dict] = []
    usage_d: Optional[Dict] = None
    platform_id = ""
    upload_files = _extract_upload_files(messages)
    proto_override = body.get("protocol", "")

    async for ch in gateway.dispatch(
        registry=request.app[REGISTRY_KEY],
        messages=_normalize_messages(messages),
        model=mdl,
        stream=False,
        tools=body.get("tools"),
        thinking=bool(extra.get("thinking")),
        search=bool(extra.get("search")),
        temperature=body.get("temperature"),
        top_p=body.get("top_p"),
        max_tokens=body.get("max_tokens"),
        stop=_sl(body.get("stop")),
        upload_files=upload_files if upload_files else None,
        protocol_id=proto_override,
        tool_choice=body.get("tool_choice"),
        platform=extra.get("platform", ""),
    ):
        if isinstance(ch, str):
            cp.append(ch)
            continue
        if isinstance(ch, dict):
            tcs, usage_d, platform_id = _collect_nonstream_dict_chunk(
                ch,
                tp,
                tcs,
                usage_d,
                platform_id,
            )
    return cp, tp, tcs, usage_d, platform_id


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
