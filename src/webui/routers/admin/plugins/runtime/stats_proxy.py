"""插件市场统计代理（本地 JSON 存储，对照 MaiBot stats_proxy）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import aiohttp.web

from src.foundation.paths import project_root

__all__ = [
    "plugins_stats_proxy_summary",
    "plugins_stats_proxy_toggle_like",
]

_STATS_FILE = project_root / "data" / "plugin_stats.json"


def _load_stats() -> Dict[str, Any]:
    if not _STATS_FILE.is_file():
        return {}
    try:
        data = json.loads(_STATS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_stats(data: Dict[str, Any]) -> None:
    _STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


async def plugins_stats_proxy_summary(request: aiohttp.web.Request) -> aiohttp.web.Response:
    plugin_id = request.match_info.get("plugin_id", "")
    stats = _load_stats()
    entry = stats.get(plugin_id, {"likes": 0, "downloads": 0, "liked": False})
    return aiohttp.web.json_response({"success": True, "stats": entry})


async def plugins_stats_proxy_toggle_like(request: aiohttp.web.Request) -> aiohttp.web.Response:
    plugin_id = request.match_info.get("plugin_id", "")
    stats = _load_stats()
    entry = dict(stats.get(plugin_id, {"likes": 0, "downloads": 0, "liked": False}))
    liked = not bool(entry.get("liked"))
    likes = int(entry.get("likes", 0))
    if liked:
        likes += 1
    elif likes > 0:
        likes -= 1
    entry["liked"] = liked
    entry["likes"] = likes
    stats[plugin_id] = entry
    _save_stats(stats)
    return aiohttp.web.json_response({"success": True, "stats": entry})
