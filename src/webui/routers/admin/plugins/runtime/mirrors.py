"""插件 Git 镜像源 CRUD（对照 MaiBot catalog mirrors）。"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List

import aiohttp.web

from src.foundation.paths import project_root

__all__ = [
    "get_plugin_mirrors",
    "plugins_mirror_create",
    "plugins_mirror_delete",
    "plugins_mirror_list",
    "plugins_mirror_update",
    "resolve_fetch_urls",
]

_MIRRORS_FILE = project_root / "data" / "plugin_mirrors.json"
_DEFAULT_MIRRORS = [
    {
        "id": "github-raw",
        "name": "GitHub Raw",
        "base_url": "https://raw.githubusercontent.com",
        "priority": 0,
        "enabled": True,
    },
]


def _load_mirrors() -> List[Dict[str, Any]]:
    if not _MIRRORS_FILE.is_file():
        return [dict(m) for m in _DEFAULT_MIRRORS]
    try:
        data = json.loads(_MIRRORS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list) and data:
            return data
    except Exception:
        pass
    return [dict(m) for m in _DEFAULT_MIRRORS]


def _save_mirrors(mirrors: List[Dict[str, Any]]) -> None:
    _MIRRORS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _MIRRORS_FILE.write_text(json.dumps(mirrors, indent=2, ensure_ascii=False), encoding="utf-8")


def get_plugin_mirrors() -> List[Dict[str, Any]]:
    mirrors = _load_mirrors()
    return sorted(
        [m for m in mirrors if m.get("enabled", True)],
        key=lambda m: int(m.get("priority", 0)),
    )


def resolve_fetch_urls(owner: str, repo: str, branch: str, file_path: str) -> List[str]:
    path = f"{owner}/{repo}/refs/heads/{branch}/{file_path}"
    urls: List[str] = []
    for mirror in get_plugin_mirrors():
        base = str(mirror.get("base_url") or "").rstrip("/")
        if base:
            urls.append(f"{base}/{path}")
    if not urls:
        urls.append(f"https://raw.githubusercontent.com/{path}")
    return urls


async def plugins_mirror_list(_request: aiohttp.web.Request) -> aiohttp.web.Response:
    return aiohttp.web.json_response({"success": True, "mirrors": _load_mirrors()})


async def plugins_mirror_create(request: aiohttp.web.Request) -> aiohttp.web.Response:
    try:
        body = await request.json()
    except Exception:
        return aiohttp.web.json_response({"success": False, "error": "invalid json"}, status=400)
    name = str(body.get("name") or "").strip()
    base_url = str(body.get("base_url") or "").strip().rstrip("/")
    if not name or not base_url:
        return aiohttp.web.json_response({"success": False, "error": "name and base_url required"}, status=400)
    mirrors = _load_mirrors()
    entry = {
        "id": str(body.get("id") or uuid.uuid4().hex[:12]),
        "name": name,
        "base_url": base_url,
        "priority": int(body.get("priority", len(mirrors))),
        "enabled": bool(body.get("enabled", True)),
    }
    mirrors.append(entry)
    _save_mirrors(mirrors)
    return aiohttp.web.json_response({"success": True, "mirror": entry})


async def plugins_mirror_update(request: aiohttp.web.Request) -> aiohttp.web.Response:
    mirror_id = request.match_info.get("mirror_id", "")
    try:
        body = await request.json()
    except Exception:
        return aiohttp.web.json_response({"success": False, "error": "invalid json"}, status=400)
    mirrors = _load_mirrors()
    for mirror in mirrors:
        if mirror.get("id") == mirror_id:
            if "name" in body:
                mirror["name"] = str(body["name"])
            if "base_url" in body:
                mirror["base_url"] = str(body["base_url"]).rstrip("/")
            if "priority" in body:
                mirror["priority"] = int(body["priority"])
            if "enabled" in body:
                mirror["enabled"] = bool(body["enabled"])
            _save_mirrors(mirrors)
            return aiohttp.web.json_response({"success": True, "mirror": mirror})
    return aiohttp.web.json_response({"success": False, "error": "not found"}, status=404)


async def plugins_mirror_delete(request: aiohttp.web.Request) -> aiohttp.web.Response:
    mirror_id = request.match_info.get("mirror_id", "")
    mirrors = [m for m in _load_mirrors() if m.get("id") != mirror_id]
    if len(mirrors) == len(_load_mirrors()):
        return aiohttp.web.json_response({"success": False, "error": "not found"}, status=404)
    _save_mirrors(mirrors)
    return aiohttp.web.json_response({"success": True})
