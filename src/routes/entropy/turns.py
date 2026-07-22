# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict

import aiohttp.web

from src.core.server import REGISTRY_KEY, clean_fncall, get_json
from src.core.utils.compat.tools import normalize_tool_calls
from src.core.utils.errors import ModerationError, NoCandidateError, ProviderError
from src.entropy.adapters.from_entropy import from_entropy_turn_body
from src.entropy.adapters.to_entropy import to_entropy_turn_response
from src.entropy.core.turn import collect_turn
from src.entropy.core.types import TurnRequest
from src.foundation.config.resolve import resolve_model
from src.foundation.logger import get_logger
from src.routes.openai.chat.helpers import _cid, _err, _json, _normalize_messages
from src.routes.openai.chat.non_stream import (
    build_chat_completion_payload,
    collect_nonstream_chat,
    fallback_parse_tool_calls,
)
from src.routes.openai.chat.stream_helpers.stream import stream_chat
from src.routes.shared.thinking import (
    resolve_include_thinking_in_history,
    resolve_thinking_config,
)

logger = get_logger(__name__)


def _is_messages_compat(body: Dict[str, Any]) -> bool:
    """WebUI 等客户端走 messages + OpenAI 响应；原生 Entropy 客户端走 input + output。"""
    return "input" not in body and isinstance(body.get("messages"), list)


def _prepare_compat_messages(body: Dict[str, Any]) -> tuple[Dict[str, Any], list]:
    extra = body.get("extra_body") or body.get("extra") or {}
    thinking_cfg = resolve_thinking_config(body, extra=extra, flavor="entropy")
    include = resolve_include_thinking_in_history(
        body, extra=extra, thinking_cfg=thinking_cfg
    )
    messages = _normalize_messages(body.get("messages", []), include_thinking_in_history=include)
    prepared = dict(body)
    prepared["messages"] = messages
    return prepared, messages


async def _create_turn_compat(
    request: aiohttp.web.Request,
    body: Dict[str, Any],
) -> aiohttp.web.StreamResponse:
    """messages 兼容层：返回 OpenAI chat.completion / SSE 形状。"""
    prepared, messages = _prepare_compat_messages(body)
    if not messages:
        return _err(400, "messages is required", "missing_field", param="messages")

    mdl = resolve_model(prepared.get("model", ""), "openai")
    if bool(prepared.get("stream", False)):
        return await stream_chat(request, prepared, thinking_flavor="entropy")

    proto_override = prepared.get("protocol", "")
    try:
        cp, tp, tcs, usage_d, platform_id = await collect_nonstream_chat(
            request, prepared, messages, mdl, thinking_flavor="entropy"
        )
    except NoCandidateError as exc:
        return _err(503, str(exc), "no_candidate", "service_unavailable")
    except ModerationError as exc:
        return _err(
            exc.status_code,
            str(exc),
            "content_policy_violation",
            "invalid_request_error",
        )
    except ProviderError as exc:
        return _err(502, str(exc), "provider_error", "upstream_error")
    except Exception as exc:
        logger.error("turn compat 异常: %s", exc, exc_info=True)
        return _err(500, str(exc), "internal_error", "server_error")

    content = "".join(cp)
    content, tcs = fallback_parse_tool_calls(
        content, tcs, platform_id, proto_override, prepared.get("tools")
    )
    tcs = normalize_tool_calls(tcs, prepared.get("tools"))
    content = clean_fncall(
        content,
        platform_id=platform_id,
        protocol_id=proto_override,
    )
    payload = build_chat_completion_payload(mdl, content, tp, tcs, usage_d)
    return _json(payload)


async def create_turn(request: aiohttp.web.Request) -> aiohttp.web.StreamResponse:
    """POST /v1/turns — Entropy 主生成端点。"""
    body = await get_json(request)
    if body is None:
        return _err(400, "Invalid JSON", "invalid_json")

    if _is_messages_compat(body):
        return await _create_turn_compat(request, body)

    turn = from_entropy_turn_body(body)
    if not turn.input:
        return _err(400, "input is required", "missing_field", param="input")

    mdl = resolve_model(body.get("model", ""), "openai")
    turn.model = mdl

    if turn.stream:
        return await _stream_turn(request, turn)

    try:
        resp_turn = await collect_turn(turn, request.app[REGISTRY_KEY])
    except Exception as exc:
        logger.error("turn 异常: %s", exc, exc_info=True)
        return _err(502, str(exc), "provider_error", "upstream_error")

    content = resp_turn.raw_text
    if resp_turn.platform_id:
        content = clean_fncall(
            content,
            platform_id=resp_turn.platform_id,
            protocol_id=turn.protocol_id,
        )
        resp_turn.raw_text = content
    payload = to_entropy_turn_response(resp_turn)
    payload["id"] = _cid()
    return _json(payload)


async def _stream_turn(
    request: aiohttp.web.Request,
    turn: TurnRequest,
) -> aiohttp.web.StreamResponse:
    from src.entropy.core.turn import execute_turn

    resp = aiohttp.web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
    await resp.prepare(request)
    async for chunk in execute_turn(turn, request.app[REGISTRY_KEY]):
        if isinstance(chunk, str):
            await resp.write(f"data: {chunk}\n\n".encode("utf-8"))
        elif isinstance(chunk, dict) and "thinking" in chunk:
            await resp.write(f"event: thinking\ndata: {chunk['thinking']}\n\n".encode())
    await resp.write(b"data: [DONE]\n\n")
    return resp


async def count_turn_tokens(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/turns/count-tokens。"""
    body = await get_json(request)
    if body is None:
        return _err(400, "Invalid JSON", "invalid_json")

    if _is_messages_compat(body):
        _, messages = _prepare_compat_messages(body)
    else:
        turn = from_entropy_turn_body(body)
        messages = turn.input

    total = sum(len(str(m.get("content", ""))) for m in messages) // 4
    return _json({"input_tokens": max(1, total)})
