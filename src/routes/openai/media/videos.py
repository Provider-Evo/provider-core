
import time
import uuid
from typing import Any, Dict

import aiohttp.web

from src.core.server import REGISTRY_KEY
from src.core.server import get_json as _get_json
from src.foundation.logger import get_logger
from src.routes.openai.chat.helpers import _err, _json, _not_supported

__all__ = [
    "create_video",
    "list_videos",
    "retrieve_video",
    "delete_video",
    "retrieve_video_content",
    "remix_video",
    "create_video_character",
    "retrieve_video_character",
    "create_video_edit",
    "create_video_extension",
    "legacy_video_generations",
]

logger = get_logger(__name__)

_VIDEOS: Dict[str, Dict[str, Any]] = {}


async def create_video(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/videos — 创建视频（能力路由）。"""
    body = await _get_json(request)
    if body is None:
        return _err(400, "Invalid JSON", "invalid_json")

    registry = request.app[REGISTRY_KEY]
    cand = await registry.get_capable_candidate("video_gen")
    if cand is None:
        return _not_supported("Video generation")

    adapter = registry.adapter_for(cand)
    try:
        result = await adapter.create_video(
            cand,
            body.get("prompt", ""),
            body.get("model", ""),
            **{k: v for k, v in body.items() if k not in ("prompt", "model")},
        )
    except NotImplementedError:
        return _not_supported("Video generation")
    except Exception as exc:
        return _err(502, str(exc), "provider_error")

    vid = (
        result.get("id")
        if isinstance(result, dict)
        else "video_{}".format(uuid.uuid4().hex[:16])
    )
    stored = {
        "id": vid,
        "object": "video",
        "created_at": int(time.time()),
        "status": "completed",
        "model": body.get("model", ""),
        "result": result,
    }
    _VIDEOS[vid] = stored
    return _json(stored)


async def list_videos(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/videos。"""
    data = list(_VIDEOS.values())
    return _json({"object": "list", "data": data})


async def retrieve_video(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/videos/{video_id}。"""
    item = _VIDEOS.get(request.match_info["video_id"])
    if item is None:
        return _err(404, "Video not found", "not_found")
    return _json(item)


async def delete_video(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """DELETE /v1/videos/{video_id}。"""
    vid = request.match_info["video_id"]
    if vid not in _VIDEOS:
        return _err(404, "Video not found", "not_found")
    del _VIDEOS[vid]
    return _json({"id": vid, "object": "video.deleted", "deleted": True})


async def retrieve_video_content(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/videos/{video_id}/content。"""
    item = _VIDEOS.get(request.match_info["video_id"])
    if item is None:
        return _err(404, "Video not found", "not_found")
    return _err(501, "Video content download not implemented", "not_implemented")


async def remix_video(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/videos/{video_id}/remix。"""
    return _not_supported("Video remix")


async def create_video_character(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/videos/characters。"""
    return _not_supported("Video characters")


async def retrieve_video_character(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """GET /v1/videos/characters/{character_id}。"""
    return _err(404, "Character not found", "not_found")


async def create_video_edit(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/videos/edits。"""
    return _not_supported("Video edits")


async def create_video_extension(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/videos/extensions。"""
    return _not_supported("Video extensions")


async def legacy_video_generations(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """POST /v1/videos/generations — 旧客户端仍走此路径，内部转发到 create_video。"""
    return await create_video(request)
