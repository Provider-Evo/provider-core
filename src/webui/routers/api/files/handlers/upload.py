"""upload 模块 — WebUI 层。

职责：
    作为 Provider-Evo 项目标准模块，提供 upload 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple

import aiohttp.web

from ..common import (
    DRIVES_SENTINEL,
    MAX_UPLOAD_SIZE,
    is_write_forbidden,
    safe_resolve,
)

"""WebUI 文件管理 API — 文件上传。"""


async def _parse_upload_multipart(
    request: aiohttp.web.Request,
) -> Tuple[str, List[tuple[str, bytes]], aiohttp.web.Response | None]:
    """解析 multipart 上传；出错时返回 error response。"""
    reader = await request.multipart()
    dir_value = ""
    pending_files: List[tuple[str, bytes]] = []

    while True:
        part = await reader.next()
        if part is None:
            break
        if part.name == "dir":
            if not dir_value:
                dir_value = (
                    (await part.read()).decode("utf-8", errors="replace").strip()
                )
            else:
                await part.read()
            continue
        if part.name != "files":
            await part.read()
            continue
        raw_name = part.filename
        if not raw_name:
            await part.read()
            continue
        filename = Path(raw_name).name
        if not filename or filename in (".", ".."):
            await part.read()
            continue
        chunks: List[bytes] = []
        total = 0
        while True:
            chunk = await part.read_chunk()
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_UPLOAD_SIZE:
                err = aiohttp.web.json_response(
                    {
                        "error": f"file '{filename}' exceeds {MAX_UPLOAD_SIZE // (1024 * 1024)} MB limit"
                    },
                    status=413,
                )
                return "", [], err
            chunks.append(chunk)
        pending_files.append((filename, b"".join(chunks)))
    return dir_value, pending_files, None


def _validate_upload_target(
    dir_value: str,
) -> Tuple[Path | None, aiohttp.web.Response | None]:
    if not dir_value:
        return None, aiohttp.web.json_response(
            {"error": "dir path is required"}, status=400
        )
    target_dir = safe_resolve(dir_value)
    if target_dir is DRIVES_SENTINEL:
        return None, aiohttp.web.json_response(
            {"error": "cannot upload to drives root; open a directory first"},
            status=400,
        )
    if target_dir is None:
        return None, aiohttp.web.json_response(
            {"error": "invalid or unsafe path"}, status=400
        )
    if not target_dir.exists():
        return None, aiohttp.web.json_response(
            {"error": "target directory does not exist"}, status=404
        )
    if not target_dir.is_dir():
        return None, aiohttp.web.json_response(
            {"error": "target path is not a directory"}, status=400
        )
    if is_write_forbidden(target_dir):
        return None, aiohttp.web.json_response(
            {"error": "uploading to this directory is not allowed"}, status=403
        )
    return target_dir, None


async def files_upload(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """中文说明：files_upload。Upload one or more files to a target directory."""
    content_type = request.content_type or ""
    if "multipart" not in content_type:
        return aiohttp.web.json_response(
            {"error": "multipart/form-data expected"}, status=400
        )

    dir_value, pending_files, parse_err = await _parse_upload_multipart(request)
    if parse_err is not None:
        return parse_err
    if not pending_files:
        return aiohttp.web.json_response({"error": "no files provided"}, status=400)

    target_dir, target_err = _validate_upload_target(dir_value)
    if target_err is not None:
        return target_err

    uploaded: List[str] = []
    skipped: List[Dict[str, str]] = []
    for filename, data in pending_files:
        dest = target_dir / filename  # type: ignore[operator]
        if is_write_forbidden(dest):
            skipped.append(
                {"file": filename, "error": "writing to this path is not allowed"}
            )
            continue
        try:
            with open(dest, "wb") as f:
                f.write(data)
            uploaded.append(filename)
        except OSError as e:
            try:
                dest.unlink(missing_ok=True)
            except OSError:
                pass
            skipped.append({"file": filename, "error": str(e)})

    if not uploaded:
        body: Dict[str, Any] = {"error": "no files uploaded"}
        if skipped:
            body["skipped"] = skipped
        return aiohttp.web.json_response(body, status=400)

    result: Dict[str, Any] = {"status": "ok", "uploaded": uploaded}
    if skipped:
        result["skipped"] = skipped
    return aiohttp.web.json_response(result)
