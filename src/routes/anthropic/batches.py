
import json
import time
import uuid
from typing import Any, Dict, List

import aiohttp.web

from src.core.server import get_json as _get_json
from src.foundation.logger import get_logger
from src.routes.anthropic.convert import _err, _json

__all__ = [
    "create_message_batch",
    "list_message_batches",
    "retrieve_message_batch",
    "cancel_message_batch",
    "retrieve_message_batch_results",
]

logger = get_logger(__name__)

_BATCHES: Dict[str, Dict[str, Any]] = {}


def _batch_id() -> str:
    return "msgbatch_{}".format(uuid.uuid4().hex[:24])


async def create_message_batch(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/messages/batches。"""
    body = await _get_json(request)
    if body is None:
        return _err(400, "Invalid JSON", "invalid_request_error")

    requests_raw = body.get("requests")
    if not isinstance(requests_raw, list) or not requests_raw:
        return _err(400, "requests is required", "invalid_request_error")

    bid = _batch_id()
    now = int(time.time())
    payload = {
        "id": bid,
        "type": "message_batch",
        "processing_status": "in_progress",
        "request_counts": {
            "processing": len(requests_raw),
            "succeeded": 0,
            "errored": 0,
            "canceled": 0,
            "expired": 0,
        },
        "ended_at": None,
        "created_at": now,
        "expires_at": now + 86400,
        "cancel_initiated_at": None,
        "results_url": "/v1/anthropic/messages/batches/{}/results".format(bid),
    }
    _BATCHES[bid] = {"meta": payload, "requests": requests_raw, "results": []}
    return _json(payload)


async def list_message_batches(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/messages/batches。"""
    data = [entry["meta"] for entry in _BATCHES.values()]
    return _json(
        {
            "data": data,
            "first_id": data[0]["id"] if data else None,
            "last_id": data[-1]["id"] if data else None,
            "has_more": False,
        }
    )


async def retrieve_message_batch(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/messages/batches/{message_batch_id}。"""
    entry = _BATCHES.get(request.match_info["message_batch_id"])
    if entry is None:
        return _err(404, "Batch not found", "not_found_error")
    return _json(entry["meta"])


async def cancel_message_batch(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/messages/batches/{message_batch_id}/cancel。"""
    bid = request.match_info["message_batch_id"]
    entry = _BATCHES.get(bid)
    if entry is None:
        return _err(404, "Batch not found", "not_found_error")
    meta = dict(entry["meta"])
    meta["processing_status"] = "canceling"
    meta["cancel_initiated_at"] = int(time.time())
    entry["meta"] = meta
    return _json(meta)


async def retrieve_message_batch_results(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """GET /v1/messages/batches/{message_batch_id}/results — JSONL 占位。"""
    entry = _BATCHES.get(request.match_info["message_batch_id"])
    if entry is None:
        return _err(404, "Batch not found", "not_found_error")
    lines: List[str] = []
    for item in entry.get("results", []):
        lines.append(json.dumps(item, ensure_ascii=False))
    body = "\n".join(lines)
    if not body:
        body = ""
    return aiohttp.web.Response(text=body, content_type="application/x-jsonlines")
