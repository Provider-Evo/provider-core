"""chat_media 模块 — WebUI 层。

职责：
    作为 Provider-Evo 项目标准模块，提供 chat_media 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""



import base64
import json
import re
from pathlib import Path

import aiohttp.web

from src.foundation.paths import persist_dir

__all__ = ["chat_media_put", "chat_media_get"]

_MEDIA_ID_RE = re.compile(r"^[a-f0-9]{16,64}$")
_MAX_BYTES = 20 * 1024 * 1024


def _media_dir() -> Path:
    path = persist_dir("webui", "chat-media")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _valid_media_id(media_id: str) -> bool:
    return bool(media_id and _MEDIA_ID_RE.match(media_id))


def _meta_path(media_id: str) -> Path:
    return _media_dir() / f"{media_id}.meta.json"


def _blob_path(media_id: str) -> Path:
    return _media_dir() / media_id


async def chat_media_put(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/webui/chat-media — 写入聊天附件（JSON: id, name, mime, data_b64）。"""
    try:
        body = await request.json()
    except Exception:
        return aiohttp.web.json_response({"error": "invalid JSON body"}, status=400)

    media_id = str(body.get("id") or "").strip()
    if not _valid_media_id(media_id):
        return aiohttp.web.json_response({"error": "invalid id"}, status=400)

    data_b64 = body.get("data_b64")
    if not isinstance(data_b64, str) or not data_b64:
        return aiohttp.web.json_response({"error": "missing data_b64"}, status=400)

    try:
        raw = base64.b64decode(data_b64, validate=True)
    except Exception:
        return aiohttp.web.json_response({"error": "invalid base64"}, status=400)

    if len(raw) > _MAX_BYTES:
        return aiohttp.web.json_response(
            {"error": f"file too large (max {_MAX_BYTES} bytes)"},
            status=400,
        )

    name = str(body.get("name") or "attachment").strip() or "attachment"
    mime = str(body.get("mime") or "application/octet-stream").strip() or "application/octet-stream"

    blob_path = _blob_path(media_id)
    meta_path = _meta_path(media_id)
    blob_path.write_bytes(raw)
    meta_path.write_text(
        json.dumps({"name": name, "mime": mime}, ensure_ascii=False),
        encoding="utf-8",
    )
    return aiohttp.web.json_response({"status": "ok", "id": media_id})


async def chat_media_get(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/webui/chat-media/{id} — 读取聊天附件。"""
    media_id = request.match_info.get("id", "")
    if not _valid_media_id(media_id):
        return aiohttp.web.json_response({"error": "invalid id"}, status=400)

    blob_path = _blob_path(media_id)
    if not blob_path.is_file():
        return aiohttp.web.json_response({"error": "not found"}, status=404)

    mime = "application/octet-stream"
    meta_path = _meta_path(media_id)
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(meta, dict) and meta.get("mime"):
                mime = str(meta["mime"])
        except Exception:
            pass

    return aiohttp.web.FileResponse(blob_path, headers={"Content-Type": mime})
