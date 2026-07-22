
import json
import time
import uuid
from typing import Any, Callable, Dict, Tuple

import aiohttp.web

from src.webui.data.services.logs.request_log import request_broker
from src.webui.data.services.stats import get_stats

__all__ = ["stats_middleware", "PARSED_JSON_BODY_KEY"]

PARSED_JSON_BODY_KEY = "_parsed_json_body"

_DEFAULT_API_PREFIXES = (
    "/v1/turns",
    "/v1/openai/chat/",
    "/v1/openai/completions",
    "/v1/anthropic/messages",
    "/v1/models",
    "/v1/openai/embeddings",
)


def _truncate_messages(messages: list) -> list:
    display: list = []
    for msg in messages:
        m = dict(msg)
        content = m.get("content", "")
        if isinstance(content, str) and len(content) > 500:
            m["content"] = content[:500] + "...(truncated)"
        elif isinstance(content, list):
            text = str(content)
            m["content"] = text[:500] + ("...(truncated)" if len(text) > 500 else "")
        display.append(m)
    return display


def _body_info_from_json(body: Dict[str, Any], *, track_live: bool) -> Dict[str, Any]:
    """Build stats body_info from a parsed JSON request body."""
    model = body.get("model", "")
    messages = body.get("messages", [])
    return {
        "model": model,
        "messages_count": len(messages),
        "messages": _truncate_messages(messages) if track_live else [],
        "has_tools": bool(body.get("tools")),
        "stream": bool(body.get("stream", False)),
    }


async def _parse_request_body(
    request: aiohttp.web.Request,
    track_live: bool,
) -> Dict[str, Any]:
    """Parse the JSON request body and build the body_info dict for stats events."""
    try:
        if request.content_type != "application/json":
            return {}
        body = await request.json()
    except Exception:
        return {}

    request[PARSED_JSON_BODY_KEY] = body
    return _body_info_from_json(body, track_live=track_live)


def _extract_response_content(response: aiohttp.web.StreamResponse) -> str:
    """Extract concatenated message content from a non-streaming JSON response body."""
    if not hasattr(response, "body") or not response.body:
        return ""
    try:
        body_bytes = (
            response.body
            if isinstance(response.body, bytes)
            else response.body.encode("utf-8")
        )
        text = body_bytes.decode("utf-8", errors="replace")
        resp_data = json.loads(text)
        content = ""
        for choice in resp_data.get("choices", []):
            msg = choice.get("message", {})
            content += msg.get("content", "") or ""
        if content:
            return content
        err = resp_data.get("error")
        if isinstance(err, dict):
            return str(err.get("message") or "")
        if isinstance(err, str):
            return err
        return ""
    except Exception:
        return ""


def _record_and_emit_end(
    request: aiohttp.web.Request,
    req_id: str,
    start: float,
    start_wall: float,
    status: int,
    platform: str,
    model: str,
    body_info: Dict[str, Any],
) -> None:
    """Record stats and push the request_end event; called from the finally block."""
    stats = get_stats()
    broker = request_broker
    latency_ms = (time.monotonic() - start) * 1000
    stats.record(
        platform=platform,
        model=model,
        status=status,
        latency_ms=latency_ms,
    )
    chunks = request.get("_req_log_chunks", [])
    response_text = "".join(str(chunk) for chunk in chunks)
    broker.push_event(
        {
            "type": "request_end",
            "id": req_id,
            "ts": start_wall,
            "status": status,
            "latency_ms": round(latency_ms, 1),
            "platform": platform,
            "model": model,
            "messages_count": body_info.get("messages_count", 0),
            "messages": body_info.get("messages", []),
            "has_tools": body_info.get("has_tools", False),
            "stream": body_info.get("stream", False),
            "response": response_text,
        }
    )


async def _run_handler_and_track(
    request: aiohttp.web.Request,
    handler: Callable,
    body_info: Dict[str, Any],
    state: Dict[str, Any],
) -> aiohttp.web.StreamResponse:
    """执行下游 handler，跟踪状态码/平台并记录响应内容，从 stats_middleware 抽出。"""
    try:
        response = await handler(request)
        state["status"] = response.status
        if hasattr(response, "_platform"):
            state["platform"] = response._platform

        if not body_info.get("stream"):
            content = _extract_response_content(response)
            if content:
                request["_req_log_chunks"].append(content)

        return response
    except aiohttp.web.HTTPException as exc:
        state["status"] = exc.status
        raise
    except Exception:
        state["status"] = 500
        raise


@aiohttp.web.middleware
async def stats_middleware(
    request: aiohttp.web.Request,
    handler: Callable,
) -> aiohttp.web.StreamResponse:
    path = request.path
    if not any(path.startswith(p) for p in _DEFAULT_API_PREFIXES):
        return await handler(request)
    if request.method != "POST":
        return await handler(request)

    broker = request_broker
    start = time.monotonic()
    start_wall = time.time()
    state: Dict[str, Any] = {"status": 200, "platform": ""}
    req_id = uuid.uuid4().hex[:16]
    track_live = broker.has_listeners

    body_info = await _parse_request_body(request, track_live)
    model = body_info.get("model", "")

    broker.push_event(
        {
            "type": "request_start",
            "id": req_id,
            "ts": start_wall,
            **body_info,
        }
    )

    request["_req_log_id"] = req_id
    request["_req_log_chunks"] = []

    try:
        return await _run_handler_and_track(request, handler, body_info, state)
    finally:
        _record_and_emit_end(
            request,
            req_id,
            start,
            start_wall,
            state["status"],
            state["platform"],
            model,
            body_info,
        )
