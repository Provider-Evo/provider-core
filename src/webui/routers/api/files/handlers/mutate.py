
import shutil
from pathlib import Path
from typing import Any, Dict, List

import aiohttp.web

from ..common import (
    DRIVES_SENTINEL,
    MAX_PREVIEW_SIZE,
    MAX_UPLOAD_SIZE,
    PROJECT_ROOT,
    SEARCH_SKIP_DIRS,
    entry_info_from_scandir,
    get_drives,
    is_binary_file,
    is_write_forbidden,
    safe_resolve,
    unique_dest,
)

"""WebUI 文件管理 API — 目录与文件变更。"""

# ---------------------------------------------------------------------------
# POST /v1/webui/files/mkdir
# ---------------------------------------------------------------------------


async def files_mkdir(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """Create a new directory."""
    try:
        body = await request.json()
    except Exception:
        return aiohttp.web.json_response({"error": "invalid JSON"}, status=400)

    rel_path = body.get("path", "")
    if not rel_path:
        return aiohttp.web.json_response(
            {"error": "path is required"},
            status=400,
        )

    target = safe_resolve(rel_path)
    if target is None or target is DRIVES_SENTINEL:
        return aiohttp.web.json_response(
            {"error": "invalid or unsafe path"},
            status=400,
        )

    try:
        target.mkdir(parents=True, exist_ok=True)
        return aiohttp.web.json_response({"status": "ok", "path": rel_path})
    except OSError as e:
        return aiohttp.web.json_response({"error": str(e)}, status=500)


# ---------------------------------------------------------------------------
# POST /v1/webui/files/delete
# ---------------------------------------------------------------------------


async def files_delete(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """Delete one or more files/directories."""
    try:
        body = await request.json()
    except Exception:
        return aiohttp.web.json_response({"error": "invalid JSON"}, status=400)

    paths = body.get("paths", [])
    if not paths or not isinstance(paths, list):
        return aiohttp.web.json_response(
            {"error": "paths array is required"},
            status=400,
        )

    results: List[Dict[str, Any]] = []
    for rel_path in paths:
        target = safe_resolve(str(rel_path))
        if target is None or target is DRIVES_SENTINEL:
            results.append({"path": rel_path, "ok": False, "error": "unsafe path"})
            continue

        try:
            if target.is_dir():
                shutil.rmtree(target)
            elif target.is_file():
                target.unlink()
            else:
                results.append({"path": rel_path, "ok": False, "error": "not found"})
                continue
            results.append({"path": rel_path, "ok": True})
        except OSError as e:
            results.append({"path": rel_path, "ok": False, "error": str(e)})

    return aiohttp.web.json_response({"results": results})


# ---------------------------------------------------------------------------
# POST /v1/webui/files/rename
# ---------------------------------------------------------------------------


async def files_rename(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """Rename or move a file/directory."""
    try:
        body = await request.json()
    except Exception:
        return aiohttp.web.json_response({"error": "invalid JSON"}, status=400)

    old_path = body.get("old_path", "")
    new_path = body.get("new_path", "")
    if not old_path or not new_path:
        return aiohttp.web.json_response(
            {"error": "old_path and new_path are required"},
            status=400,
        )

    src = safe_resolve(old_path)
    dst = safe_resolve(new_path)
    if src is None or dst is None or src is DRIVES_SENTINEL or dst is DRIVES_SENTINEL:
        return aiohttp.web.json_response(
            {"error": "invalid or unsafe path"},
            status=400,
        )

    if not src.exists():
        return aiohttp.web.json_response(
            {"error": "source path not found"},
            status=404,
        )

    try:
        # Create parent dirs if needed
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
        return aiohttp.web.json_response({"status": "ok"})
    except OSError as e:
        return aiohttp.web.json_response({"error": str(e)}, status=500)


# ---------------------------------------------------------------------------
# POST /v1/webui/files/write
# ---------------------------------------------------------------------------


async def files_write(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """Save file content to disk."""
    try:
        body = await request.json()
    except Exception:
        return aiohttp.web.json_response({"error": "invalid JSON"}, status=400)

    rel_path = body.get("path", "")
    content = body.get("content")
    if not rel_path:
        return aiohttp.web.json_response({"error": "path is required"}, status=400)
    if content is None:
        return aiohttp.web.json_response({"error": "content is required"}, status=400)
    if not isinstance(content, str):
        return aiohttp.web.json_response(
            {"error": "content must be a string"}, status=400
        )

    target = safe_resolve(rel_path)
    if target is None or target is DRIVES_SENTINEL:
        return aiohttp.web.json_response(
            {"error": "invalid or unsafe path"}, status=400
        )
    if is_write_forbidden(target):
        return aiohttp.web.json_response(
            {"error": "writing to this path is not allowed"}, status=403
        )

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return aiohttp.web.json_response({"status": "ok"})
    except PermissionError:
        return aiohttp.web.json_response({"error": "permission denied"}, status=403)
    except OSError as e:
        return aiohttp.web.json_response({"error": str(e)}, status=500)
