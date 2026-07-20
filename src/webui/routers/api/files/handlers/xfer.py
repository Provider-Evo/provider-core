
import shutil
from pathlib import Path
from typing import Any, Dict

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

"""WebUI 文件管理 API — 复制与移动。"""

# ---------------------------------------------------------------------------
# POST /v1/webui/files/copy
# ---------------------------------------------------------------------------


def _resolve_copy_dest(src: Path, dst: Path) -> Path:
    if dst.is_dir():
        dst = dst / src.name
    return unique_dest(dst)


async def files_copy(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """Copy a file or directory."""
    try:
        body = await request.json()
    except Exception:
        return aiohttp.web.json_response({"error": "invalid JSON"}, status=400)

    source_rel = body.get("source", "")
    dest_rel = body.get("dest", "")
    if not source_rel or not dest_rel:
        return aiohttp.web.json_response(
            {"error": "source and dest are required"}, status=400
        )

    src = safe_resolve(source_rel)
    dst = safe_resolve(dest_rel)
    if src is None or dst is None or src is DRIVES_SENTINEL or dst is DRIVES_SENTINEL:
        return aiohttp.web.json_response(
            {"error": "invalid or unsafe path"}, status=400
        )
    if not src.exists():
        return aiohttp.web.json_response({"error": "source path not found"}, status=404)
    if is_write_forbidden(dst):
        return aiohttp.web.json_response(
            {"error": "copying to this path is not allowed"}, status=403
        )

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


def _move_json_error(message: str, status: int) -> aiohttp.web.Response:
    return aiohttp.web.json_response({"error": message}, status=status)


async def _resolve_move_paths(
    request: aiohttp.web.Request,
) -> tuple:
    try:
        body = await request.json()
    except Exception:
        return _move_json_error("invalid JSON", 400), None, None

    source_rel = body.get("source", "")
    dest_rel = body.get("dest", "")
    if not source_rel or not dest_rel:
        return _move_json_error("source and dest are required", 400), None, None

    src = safe_resolve(source_rel)
    dst = safe_resolve(dest_rel)
    if src is None or dst is None or src is DRIVES_SENTINEL or dst is DRIVES_SENTINEL:
        return _move_json_error("invalid or unsafe path", 400), None, None
    if not src.exists():
        return _move_json_error("source path not found", 404), None, None
    if is_write_forbidden(dst):
        return _move_json_error("moving to this path is not allowed", 403), None, None
    if dst.is_dir():
        dst = dst / src.name
    return None, src, unique_dest(dst)


async def files_move(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """Move a file or directory."""
    err_resp, src, dst = await _resolve_move_paths(request)
    if err_resp is not None:
        return err_resp

    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return aiohttp.web.json_response({"status": "ok", "dest": str(dst)})
    except OSError as e:
        return aiohttp.web.json_response({"error": str(e)}, status=500)
