
import time
import uuid
from typing import Any, Dict, List, Optional

import aiohttp.web

from src.core.server import REGISTRY_KEY
from src.core.server import clean_fncall as _clean_fncall
from src.core.server import get_json as _get_json
from src.core.utils.compat.tools import normalize_content
from src.core.utils.errors import NoCandidateError, ProviderError
from src.foundation.logger import get_logger
from src.routes.openai.chat.helpers import (
    _err,
    _json,
    _normalize_messages,
    _not_supported,
)

__all__ = [
    "create_response",
    "retrieve_response",
    "delete_response",
    "cancel_response",
    "list_input_items",
    "compact_responses",
    "count_input_tokens",
]

logger = get_logger(__name__)

_RESPONSES: Dict[str, Dict[str, Any]] = {}


def _response_messages(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从 Responses API 请求体构造 OpenAI 风格 messages。"""
    input_data = body.get("input", "")
    if isinstance(input_data, str):
        messages: List[Dict[str, Any]] = [{"role": "user", "content": input_data}]
    elif isinstance(input_data, list):
        messages = _normalize_messages(input_data)
    else:
        messages = [{"role": "user", "content": str(input_data)}]
    instructions = body.get("instructions")
    if instructions:
        instructions_str = normalize_content(instructions)
        if instructions_str:
            messages.insert(0, {"role": "system", "content": instructions_str})
    return messages


async def _dispatch_response_content(
    registry: Any,
    messages: List[Dict[str, Any]],
    mdl: str,
    tools: Optional[List[Dict[str, Any]]],
) -> tuple[str, Optional[Dict[str, Any]]]:
    """调用网关并返回拼接内容与 usage。"""
    from src.core import gateway

    cp: List[str] = []
    usage_d: Optional[Dict[str, Any]] = None
    async for ch in gateway.dispatch(
        registry=registry,
        messages=messages,
        model=mdl,
        stream=False,
        tools=tools,
    ):
        if isinstance(ch, str):
            cp.append(ch)
        elif isinstance(ch, dict) and "usage" in ch:
            usage_d = ch["usage"]
    return _clean_fncall("".join(cp)), usage_d


def _store_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    _RESPONSES[payload["id"]] = payload
    return payload


def _get_stored(response_id: str) -> Optional[Dict[str, Any]]:
    return _RESPONSES.get(response_id)


def _build_response_payload(
    mdl: str,
    content: str,
    messages: List[Dict[str, Any]],
    usage_d: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """构造 /v1/responses 返回体。"""
    resp_id = "resp_{}".format(uuid.uuid4().hex[:24])
    msg_id = "msg_{}".format(uuid.uuid4().hex[:16])
    return {
        "id": resp_id,
        "object": "response",
        "created_at": int(time.time()),
        "status": "completed",
        "model": mdl,
        "output": [
            {
                "type": "message",
                "id": msg_id,
                "role": "assistant",
                "content": [{"type": "output_text", "text": content}],
            }
        ],
        "usage": usage_d
        or {
            "input_tokens": sum(len(str(m.get("content", ""))) // 3 for m in messages),
            "output_tokens": len(content) // 3,
            "total_tokens": 0,
        },
    }


async def create_response(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/responses — 创建响应并存储。"""
    body = await _get_json(request)
    if body is None:
        return _err(400, "Invalid JSON", "invalid_json")

    registry = request.app[REGISTRY_KEY]
    cands = await registry.get_candidates(capability="responses")
    if not cands:
        cands = await registry.get_candidates(capability="chat")
    if not cands:
        return _not_supported("Responses")

    mdl = body.get("model", "")
    messages = _response_messages(body)
    tools_raw = body.get("tools")
    tools: Optional[List[Dict[str, Any]]] = None
    if tools_raw:
        tools = [t for t in tools_raw if t.get("type") == "function"]

    try:
        content, usage_d = await _dispatch_response_content(
            registry, messages, mdl, tools
        )
    except NoCandidateError as exc:
        return _err(503, str(exc), "no_candidate")
    except ProviderError as exc:
        return _err(502, str(exc), "provider_error")

    payload = _build_response_payload(mdl, content, messages, usage_d)
    return _json(_store_response(payload))


async def retrieve_response(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/responses/{response_id}。"""
    stored = _get_stored(request.match_info["response_id"])
    if stored is None:
        return _err(404, "Response not found", "not_found")
    return _json(stored)


async def delete_response(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """DELETE /v1/responses/{response_id}。"""
    rid = request.match_info["response_id"]
    if rid not in _RESPONSES:
        return _err(404, "Response not found", "not_found")
    del _RESPONSES[rid]
    return _json({"id": rid, "object": "response.deleted", "deleted": True})


async def cancel_response(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/responses/{response_id}/cancel。"""
    stored = _get_stored(request.match_info["response_id"])
    if stored is None:
        return _err(404, "Response not found", "not_found")
    stored = dict(stored)
    stored["status"] = "cancelled"
    _RESPONSES[stored["id"]] = stored
    return _json(stored)


async def list_input_items(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/responses/{response_id}/input_items。"""
    stored = _get_stored(request.match_info["response_id"])
    if stored is None:
        return _err(404, "Response not found", "not_found")
    return _json(
        {
            "object": "list",
            "data": [],
            "first_id": None,
            "last_id": None,
            "has_more": False,
        }
    )


async def compact_responses(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/responses/compact — 501 占位。"""
    return _not_supported("Responses compact")


async def count_input_tokens(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/responses/input_tokens — 估算 input tokens。"""
    body = await _get_json(request) or {}
    messages = _response_messages(body)
    estimated = sum(len(str(m.get("content", ""))) // 3 for m in messages)
    return _json({"input_tokens": estimated, "object": "response.input_tokens"})
