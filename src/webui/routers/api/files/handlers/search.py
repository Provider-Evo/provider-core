
import os
import stat
from pathlib import Path
from typing import Any, Dict, List

import aiohttp.web

from ..common import (
    DRIVES_SENTINEL,
    SEARCH_SKIP_DIRS,
    safe_resolve,
)

"""WebUI 文件管理 API — 文件搜索。"""


def _match_search_entry(
    entry_path: Path,
    query_lower: str,
    exact: List[Dict[str, Any]],
    prefix: List[Dict[str, Any]],
    substring: List[Dict[str, Any]],
) -> None:
    name_lower = entry_path.name.lower()
    if name_lower == query_lower:
        bucket = exact
    elif name_lower.startswith(query_lower):
        bucket = prefix
    elif query_lower in name_lower:
        bucket = substring
    else:
        return
    try:
        st = entry_path.stat()
    except OSError:
        return
    is_dir = stat.S_ISDIR(st.st_mode)
    bucket.append(
        {
            "name": entry_path.name,
            "path": str(entry_path),
            "is_dir": is_dir,
            "size": st.st_size if not is_dir else None,
            "modified": st.st_mtime,
        }
    )


def _walk_search(
    target: Path,
    query_lower: str,
    recursive: bool,
    exact: List[Dict[str, Any]],
    prefix: List[Dict[str, Any]],
    substring: List[Dict[str, Any]],
    max_results: int,
) -> None:
    found = 0

    def _maybe_add(entry_path: Path) -> bool:
        nonlocal found
        before = found
        _match_search_entry(entry_path, query_lower, exact, prefix, substring)
        found = len(exact) + len(prefix) + len(substring)
        return found > before

    if recursive:
        for dirpath, dirnames, filenames in os.walk(str(target)):
            if len(exact) + len(prefix) + len(substring) >= max_results:
                return
            dirnames[:] = [d for d in dirnames if d not in SEARCH_SKIP_DIRS]
            dp = Path(dirpath)
            for name in filenames + dirnames:
                _maybe_add(dp / name)
                if len(exact) + len(prefix) + len(substring) >= max_results:
                    return
        return
    try:
        for child in target.iterdir():
            _match_search_entry(child, query_lower, exact, prefix, substring)
    except PermissionError:
        pass


async def files_search(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """Search files by name within a directory tree."""
    dir_rel = request.query.get("dir", "")
    query = request.query.get("query", "")
    if not dir_rel:
        return aiohttp.web.json_response({"error": "dir is required"}, status=400)
    if not query:
        return aiohttp.web.json_response({"error": "query is required"}, status=400)

    target = safe_resolve(dir_rel)
    if target is None or target is DRIVES_SENTINEL:
        return aiohttp.web.json_response(
            {"error": "invalid or unsafe path"}, status=400
        )
    if not target.exists():
        return aiohttp.web.json_response({"error": "directory not found"}, status=404)
    if not target.is_dir():
        return aiohttp.web.json_response(
            {"error": "path is not a directory"}, status=400
        )

    recursive = request.query.get("recursive", "true").lower() != "false"
    try:
        max_results = int(request.query.get("max_results", "100"))
    except (ValueError, TypeError):
        max_results = 100
    max_results = max(1, min(max_results, 500))

    exact: List[Dict[str, Any]] = []
    prefix: List[Dict[str, Any]] = []
    substring: List[Dict[str, Any]] = []
    query_lower = query.lower()

    try:
        _walk_search(
            target, query_lower, recursive, exact, prefix, substring, max_results
        )
    except PermissionError:
        return aiohttp.web.json_response({"error": "permission denied"}, status=403)

    sort_key = lambda item: item["name"].lower()
    exact.sort(key=sort_key)
    prefix.sort(key=sort_key)
    substring.sort(key=sort_key)
    return aiohttp.web.json_response(
        {"results": (exact + prefix + substring)[:max_results]}
    )
