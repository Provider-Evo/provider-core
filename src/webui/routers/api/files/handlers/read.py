from __future__ import annotations

import aiohttp.web
import base64
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .._common import (
    DRIVES_SENTINEL,
    MAX_PREVIEW_SIZE,
    PROJECT_ROOT,
    entry_info_from_scandir,
    get_drives,
    is_binary_file,
    safe_resolve,
)


"""WebUI 文件管理 API — 列表、读取与下载。"""


def _parse_list_pagination(request: aiohttp.web.Request) -> Tuple[int, int]:
    try:
        offset = max(0, int(request.query.get("offset", 0)))
    except (ValueError, TypeError):
        offset = 0
    try:
        limit = max(1, min(int(request.query.get("limit", 200)), 1000))
    except (ValueError, TypeError):
        limit = 200
    return offset, limit


def _drive_entries() -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for drive in get_drives():
        drive_path = Path(drive)
        try:
            st = drive_path.stat()
            modified = st.st_mtime
        except OSError:
            modified = 0
        entries.append({
            "name": drive.rstrip("\\").rstrip("/"),
            "type": "dir",
            "size": None,
            "modified": modified,
            "path": drive,
        })
    return entries


def _list_dir_entries(target: Path, offset: int, limit: int) -> Tuple[List[Dict[str, Any]], int]:
    all_entries = list(os.scandir(str(target)))
    all_entries.sort(key=lambda e: (not e.is_dir(), e.name.lower()))
    total = len(all_entries)
    entries = []
    for entry in all_entries[offset:offset + limit]:
        info = entry_info_from_scandir(entry)
        if info:
            entries.append(info)
    return entries, total


async def files_list(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """中文说明：files_list。List directory contents with pagination."""
    rel_path = request.query.get("path", "/")
    offset, limit = _parse_list_pagination(request)
    target = safe_resolve(rel_path)

    if target is DRIVES_SENTINEL:
        entries = _drive_entries()
        return aiohttp.web.json_response({
            "entries": entries[offset:offset + limit],
            "total": len(entries),
            "offset": offset,
            "limit": limit,
            "path": "/",
            "root": str(PROJECT_ROOT),
            "isDrives": True,
        })

    if target is None:
        return aiohttp.web.json_response({"error": "invalid or unsafe path"}, status=400)
    if not target.exists():
        return aiohttp.web.json_response({"error": "path not found"}, status=404)
    if not target.is_dir():
        return aiohttp.web.json_response({"error": "path is not a directory"}, status=400)

    try:
        entries, total = _list_dir_entries(target, offset, limit)
    except PermissionError:
        return aiohttp.web.json_response({"error": "permission denied"}, status=403)

    return aiohttp.web.json_response({
        "entries": entries,
        "total": total,
        "offset": offset,
        "limit": limit,
        "path": str(target),
        "root": str(PROJECT_ROOT),
    })


def _read_image_preview(target: Path, total_size: int) -> aiohttp.web.Response:
    ext = target.suffix.lower()
    if ext not in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".ico", ".svg"):
        return aiohttp.web.json_response({
            "content": None,
            "encoding": "binary",
            "total_size": total_size,
            "truncated": False,
        })
    try:
        with open(target, "rb") as f:
            data = f.read(MAX_PREVIEW_SIZE)
        mime = mimetypes.guess_type(str(target))[0] or "image/png"
        b64 = base64.b64encode(data).decode("ascii")
        return aiohttp.web.json_response({
            "content": f"data:{mime};base64,{b64}",
            "encoding": "base64",
            "total_size": total_size,
            "truncated": total_size > MAX_PREVIEW_SIZE,
        })
    except OSError as e:
        return aiohttp.web.json_response({"error": str(e)}, status=500)


def _read_text_preview(target: Path, total_size: int, offset: int, limit: int) -> aiohttp.web.Response:
    try:
        with open(target, "r", encoding="utf-8", errors="replace") as f:
            if offset > 0:
                for _ in range(offset):
                    f.readline()
            lines: List[str] = []
            for _ in range(limit):
                line = f.readline()
                if not line:
                    break
                lines.append(line)
        total_lines = 0
        with open(target, "r", encoding="utf-8", errors="replace") as f:
            for _ in f:
                total_lines += 1
        return aiohttp.web.json_response({
            "content": "".join(lines),
            "encoding": "utf-8",
            "total_size": total_size,
            "total_lines": total_lines,
            "offset": offset,
            "limit": limit,
            "truncated": total_size > MAX_PREVIEW_SIZE,
        })
    except OSError as e:
        return aiohttp.web.json_response({"error": str(e)}, status=500)


async def files_read(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """中文说明：files_read。Read file content for preview."""
    rel_path = request.query.get("path", "")
    if not rel_path:
        return aiohttp.web.json_response({"error": "path is required"}, status=400)

    target = safe_resolve(rel_path)
    if target is None or target is DRIVES_SENTINEL:
        return aiohttp.web.json_response({"error": "invalid or unsafe path"}, status=400)
    if not target.is_file():
        return aiohttp.web.json_response({"error": "path is not a file"}, status=400)

    total_size = target.stat().st_size
    if is_binary_file(target):
        return _read_image_preview(target, total_size)

    offset = int(request.query.get("offset", 0))
    limit = int(request.query.get("limit", 500))
    return _read_text_preview(target, total_size, offset, limit)


async def files_download(request: aiohttp.web.Request) -> aiohttp.web.StreamResponse:
    """中文说明：files_download。Download a file as attachment."""
    rel_path = request.query.get("path", "")
    if not rel_path:
        return aiohttp.web.json_response({"error": "path is required"}, status=400)

    target = safe_resolve(rel_path)
    if target is None or target is DRIVES_SENTINEL:
        return aiohttp.web.json_response({"error": "invalid or unsafe path"}, status=400)
    if not target.is_file():
        return aiohttp.web.json_response({"error": "path is not a file"}, status=400)

    mime = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
    resp = aiohttp.web.StreamResponse(
        status=200,
        headers={
            "Content-Type": mime,
            "Content-Disposition": f'attachment; filename="{target.name}"',
            "Content-Length": str(target.stat().st_size),
        },
    )
    await resp.prepare(request)
    try:
        with open(target, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                await resp.write(chunk)
    except OSError:
        pass
    await resp.write_eof()
    return resp
