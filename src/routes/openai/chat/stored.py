"""stored 模块 — HTTP 入口路由。

职责：
    作为 Provider-Evo 项目标准模块，提供 stored 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""



import time
from typing import Any, Dict

import aiohttp.web

from src.core.server import get_json as _get_json
from src.routes.openai.chat.helpers import _cid, _err, _json, _not_supported

__all__ = [
    "delete_stored_completion",
    "update_stored_completion",
    "retrieve_stored_completion",
    "list_stored_completion_messages",
]

_STORED: Dict[str, Dict[str, Any]] = {}


async def retrieve_stored_completion(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/chat/completions/{completion_id}。"""
    item = _STORED.get(request.match_info["completion_id"])
    if item is None:
        return _err(404, "Completion not found", "not_found")
    return _json(item)


async def update_stored_completion(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/chat/completions/{completion_id}。"""
    return _not_supported("Stored chat completion update")


async def delete_stored_completion(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """DELETE /v1/chat/completions/{completion_id}。"""
    cid = request.match_info["completion_id"]
    if cid not in _STORED:
        return _err(404, "Completion not found", "not_found")
    del _STORED[cid]
    return _json({"id": cid, "object": "chat.completion.deleted", "deleted": True})


async def list_stored_completion_messages(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/chat/completions/{completion_id}/messages。"""
    item = _STORED.get(request.match_info["completion_id"])
    if item is None:
        return _err(404, "Completion not found", "not_found")
    return _json({"object": "list", "data": item.get("messages", []), "has_more": False})


def remember_completion(payload: Dict[str, Any]) -> None:
    """供 chat 路由可选调用，写入 stored completion。"""
    cid = payload.get("id") or _cid()
    payload = dict(payload)
    payload["id"] = cid
    payload.setdefault("object", "chat.completion")
    payload.setdefault("created", int(time.time()))
    _STORED[cid] = payload
