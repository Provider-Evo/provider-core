
import time
from typing import Any, Dict, List, Optional

import aiohttp.web

from src.core.server import REGISTRY_KEY
from src.core.server import clean_fncall as _clean_fncall
from src.core.server import get_json as _get_json
from src.core.utils.errors import NoCandidateError, ProviderError
from src.foundation.config.resolve import resolve_model
from src.foundation.logger import get_logger
from src.routes.openai.chat.helpers import _err, _id, _json, _not_supported, _sl
from src.routes.openai.chat.non_stream import (
    build_chat_completion_payload,
    collect_nonstream_chat,
    fallback_parse_tool_calls,
)

__all__ = ["completions"]

logger = get_logger(__name__)


def _body_to_chat(body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """将 legacy completions 请求体转为 chat completions 形态。"""
    prompt = body.get("prompt")
    if prompt is None or prompt == "":
        return None
    if isinstance(prompt, list):
        text = "".join(str(p) for p in prompt)
    else:
        text = str(prompt)
    suffix = body.get("suffix")
    if suffix:
        text = text + str(suffix)
    messages: List[Dict[str, Any]] = [{"role": "user", "content": text}]
    chat_body: Dict[str, Any] = {
        "model": body.get("model", ""),
        "messages": messages,
        "stream": bool(body.get("stream", False)),
        "temperature": body.get("temperature"),
        "top_p": body.get("top_p"),
        "max_tokens": body.get("max_tokens"),
        "stop": _sl(body.get("stop")),
        "extra_body": body.get("extra_body") or body.get("extra") or {},
    }
    echo = body.get("echo")
    if echo is not None:
        chat_body.setdefault("extra_body", {})["echo"] = echo
    return chat_body


def _to_completion_payload(
    mdl: str, text: str, usage_d: Optional[Dict]
) -> Dict[str, Any]:
    """组装 legacy completion 响应。"""
    usage = usage_d or {
        "prompt_tokens": max(1, len(text) // 4),
        "completion_tokens": max(1, len(text) // 4),
        "total_tokens": max(2, len(text) // 2),
    }
    return {
        "id": _id("cmpl"),
        "object": "text_completion",
        "created": int(time.time()),
        "model": mdl,
        "choices": [
            {
                "text": text,
                "index": 0,
                "logprobs": None,
                "finish_reason": "stop",
            }
        ],
        "usage": usage,
    }


async def completions(request: aiohttp.web.Request) -> aiohttp.web.StreamResponse:
    """遗留补全端点 POST /v1/completions。"""
    if request.method != "POST":
        return _err(405, "Use POST for /v1/completions", "method_not_allowed")

    body = await _get_json(request)
    if body is None:
        return _err(400, "Invalid JSON in request body", "invalid_json")

    chat_body = _body_to_chat(body)
    if chat_body is None:
        return _err(400, "prompt is required", "missing_field", param="prompt")

    registry = request.app[REGISTRY_KEY]
    mdl = resolve_model(chat_body.get("model", ""), "openai")
    chat_body["model"] = mdl

    cands = await registry.get_candidates(model=mdl, capability="completions")
    if not cands:
        cands = await registry.get_candidates(model=mdl, capability="chat")
    if not cands:
        return _not_supported("Completions")

    if chat_body.get("stream"):
        from src.routes.openai.chat.stream_helpers.stream import stream_chat

        return await stream_chat(request, chat_body)

    messages = chat_body["messages"]
    try:
        cp, tp, tcs, usage_d, platform_id = await collect_nonstream_chat(
            request, chat_body, messages, mdl
        )
    except NoCandidateError as exc:
        return _err(503, str(exc), "no_candidate", "service_unavailable")
    except ProviderError as exc:
        return _err(502, str(exc), "provider_error", "upstream_error")
    except Exception as exc:
        logger.error("completions 异常: %s", exc, exc_info=True)
        return _err(500, str(exc), "internal_error", "server_error")

    content = _clean_fncall("".join(cp), platform_id=platform_id)
    content, _ = fallback_parse_tool_calls(content, tcs, platform_id, "", None)
    return _json(_to_completion_payload(mdl, content, usage_d))
