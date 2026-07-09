from __future__ import annotations

import aiohttp.web
import shutil
from pathlib import Path
from typing import Any, Dict

from .._common import (
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

"""WebUI 文件管理 API — 复制与移动。"""

# ---------------------------------------------------------------------------
# POST /v1/webui/files/copy
# ---------------------------------------------------------------------------

def _resolve_copy_dest(src: Path, dst: Path) -> Path:
    if dst.is_dir():
        dst = dst / src.name
    return unique_dest(dst)


async def files_copy(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """中文说明：files_copy。Copy a file or directory."""
    try:
        body = await request.json()
    except Exception:
        return aiohttp.web.json_response({"error": "invalid JSON"}, status=400)

    source_rel = body.get("source", "")
    dest_rel = body.get("dest", "")
    if not source_rel or not dest_rel:
        return aiohttp.web.json_response({"error": "source and dest are required"}, status=400)

    src = safe_resolve(source_rel)
    dst = safe_resolve(dest_rel)
    if src is None or dst is None or src is DRIVES_SENTINEL or dst is DRIVES_SENTINEL:
        return aiohttp.web.json_response({"error": "invalid or unsafe path"}, status=400)
    if not src.exists():
        return aiohttp.web.json_response({"error": "source path not found"}, status=404)
    if is_write_forbidden(dst):
        return aiohttp.web.json_response({"error": "copying to this path is not allowed"}, status=403)

    try:
        dst = _resolve_copy_dest(src, dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(str(src), str(dst))
        else:
            shutil.copy2(str(src), str(dst))
        return aiohttp.web.json_response({"status": "ok", "dest": str(dst)})
    except OSError as e:
        return aiohttp.web.json_response({"error": str(e)}, status=500)


# ---------------------------------------------------------------------------
# POST /v1/webui/files/move
# ---------------------------------------------------------------------------

async def files_move(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """中文说明：files_move。

Move a file or directory.

Body: {"source": "/path/to/source", "dest": "/path/to/destination"}"""
    try:
        body = await request.json()
    except Exception:
        return aiohttp.web.json_response({"error": "invalid JSON"}, status=400)

    source_rel = body.get("source", "")
    dest_rel = body.get("dest", "")
    if not source_rel or not dest_rel:
        return aiohttp.web.json_response(
            {"error": "source and dest are required"}, status=400,
        )

    src = safe_resolve(source_rel)
    dst = safe_resolve(dest_rel)
    if src is None or dst is None or src is DRIVES_SENTINEL or dst is DRIVES_SENTINEL:
        return aiohttp.web.json_response(
            {"error": "invalid or unsafe path"}, status=400,
        )

    if not src.exists():
        return aiohttp.web.json_response(
            {"error": "source path not found"}, status=404,
        )

    # Block writes to sensitive paths
    if is_write_forbidden(dst):
        return aiohttp.web.json_response(
            {"error": "moving to this path is not allowed"}, status=403,
        )

    try:
        # If dest is an existing directory, move into it using source name
        if dst.is_dir():
            dst = dst / src.name

        dst = unique_dest(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)

        shutil.move(str(src), str(dst))

        return aiohttp.web.json_response({"status": "ok", "dest": str(dst)})
    except OSError as e:
        return aiohttp.web.json_response({"error": str(e)}, status=500)


