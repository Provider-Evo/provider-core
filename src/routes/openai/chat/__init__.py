# -*- coding: utf-8 -*-
from __future__ import annotations

"""OpenAI 兼容路由——Chat Completions 端点（薄聚合层）。"""

from typing import Any, Dict

import aiohttp.web

from src.core.server import clean_fncall as _clean_fncall
from src.core.server import get_json as _get_json
from src.core.utils.errors import ModerationError, NoCandidateError, ProviderError
from src.foundation.config.resolve import resolve_model
from src.foundation.logger import get_logger
from src.core.utils.compat.tools import normalize_tool_calls
from src.routes.openai.chat.helpers import _err, _json, _normalize_messages
from src.routes.openai.chat.non_stream import (
    build_chat_completion_payload,
    collect_nonstream_chat,
    fallback_parse_tool_calls,
)
from src.routes.openai.chat.stream_helpers.stream import stream_chat

__all__ = [
    "_stream_chat",
    "chat_completions",
]

logger = get_logger(__name__)

_stream_chat = stream_chat


async def _parse_chat_request(
    request: aiohttp.web.Request,
) -> "tuple[Dict[str, Any], aiohttp.web.StreamResponse | None]":
    """解析并规范化请求体，返回 (body, error_response)；error_response 非 None 表示失败。"""
    if request.method != "POST":
        return {}, _err(
            405,
            "Method {} not allowed. Use POST for /v1/chat/completions.".format(
                request.method
            ),
            "method_not_allowed",
        )

    body = await _get_json(request)
    if body is None:
        return {}, _err(400, "Invalid JSON in request body", "invalid_json")

    if "messages" in body and isinstance(body["messages"], list):
        body["messages"] = _normalize_messages(body["messages"])

    if not body.get("messages", []):
        return {}, _err(400, "messages is required", "missing_field", param="messages")

    return body, None


def _check_model_permission(
    request: aiohttp.web.Request, mdl: str, body: Dict[str, Any]
) -> aiohttp.web.StreamResponse | None:
    """校验虚拟 Key 的模型白名单；不允许时返回 403 响应，否则返回 None。"""
    vk = request.get("_virtual_key")
    if not (vk and vk.get("models")):
        return None
    allowed = set(vk["models"])
    if mdl in allowed or body.get("model", "") in allowed:
        return None
    return _err(
        403, "Model not allowed for this key", "model_not_allowed", "permission_error"
    )


async def _collect_and_build_payload(
    request: aiohttp.web.Request,
    body: Dict[str, Any],
    messages: Any,
    mdl: str,
) -> "tuple[Dict[str, Any] | None, aiohttp.web.StreamResponse | None]":
    """调用网关收集非流式响应并构建 payload；失败时返回 (None, error_response)。"""
    proto_override = body.get("protocol", "")
    try:
        cp, tp, tcs, usage_d, platform_id = await collect_nonstream_chat(
            request, body, messages, mdl
        )
    except NoCandidateError as e:
        return None, _err(503, str(e), "no_candidate", "service_unavailable")
    except ModerationError as e:
        return None, _err(
            e.status_code,
            str(e),
            "content_policy_violation",
            "invalid_request_error",
        )
    except ProviderError as e:
        return None, _err(502, str(e), "provider_error", "upstream_error")
    except Exception as e:
        logger.error("补全异常: %s", e, exc_info=True)
        return None, _err(500, str(e), "internal_error", "server_error")

    content = "".join(cp)
    content, tcs = fallback_parse_tool_calls(
        content, tcs, platform_id, proto_override, body.get("tools")
    )
    tcs = normalize_tool_calls(tcs, body.get("tools"))
    content = _clean_fncall(
        content, platform_id=platform_id, protocol_id=proto_override
    )
    payload = build_chat_completion_payload(mdl, content, tp, tcs, usage_d)
    return payload, None


async def chat_completions(
    request: aiohttp.web.Request,
) -> aiohttp.web.StreamResponse:
    """聊天补全端点 /v1/chat/completions。"""
    body, error_resp = await _parse_chat_request(request)
    if error_resp is not None:
        return error_resp

    messages = body.get("messages", [])
    mdl = resolve_model(body.get("model", ""), "openai")

    permission_error = _check_model_permission(request, mdl, body)
    if permission_error is not None:
        return permission_error

    extra = body.get("extra_body") or body.get("extra") or {}
    thinking = bool(extra.get("thinking"))
    search = bool(extra.get("search"))

    if bool(body.get("stream", False)):
        return await stream_chat(request, body)

    from src.core.dispatch.cache.response_cache import get_response_cache

    cache = get_response_cache()
    cache_key = cache._cache_key(
        mdl, messages, body.get("tools"), False, thinking, search
    )
    cached = cache.get(cache_key)
    if cached is not None:
        resp = _json(cached)
        resp.headers["X-Cache"] = "HIT"
        return resp

    payload, error_resp = await _collect_and_build_payload(request, body, messages, mdl)
    if error_resp is not None:
        return error_resp

    cache.put(cache_key, payload)
    vk = request.get("_virtual_key")
    if vk:
        from src.core.auth.virtual_keys import get_virtual_key_store

        await get_virtual_key_store().consume(vk["id"], 1)
    resp = _json(payload)
    resp.headers["X-Cache"] = "MISS"
    return resp
