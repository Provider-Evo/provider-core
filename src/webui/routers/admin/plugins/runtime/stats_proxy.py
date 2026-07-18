"""stats_proxy 模块 — WebUI 层。

职责：
    插件点赞代理。点赞状态与计数直接来自 GitHub：每个插件在
    plugin-repo 对应一个 tracker Issue（见 plugin_details.json 的
    likeIssueNumber 字段），点赞 = 用本机已认证的 gh CLI 身份给该
    Issue 加 +1 reaction；取消点赞 = 删除该 reaction。不落任何本地
    likes/downloads 假数据文件。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
"""


from __future__ import annotations

import json
import subprocess
from typing import Any, Dict, Optional

import aiohttp.web

from src.foundation.logger import get_logger
from src.foundation.paths import project_root
from src.webui.routers.admin.plugins.plugin_support import DEFAULT_PLUGIN_REPO

__all__ = [
    "plugins_stats_proxy_summary",
    "plugins_stats_proxy_toggle_like",
]

logger = get_logger(__name__)

_GH_TIMEOUT = 20
_cached_login: Optional[str] = None


def _gh_json(args: list) -> Any:
    proc = subprocess.run(
        ["gh"] + args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=_GH_TIMEOUT,
        check=True,
    )
    return json.loads(proc.stdout) if proc.stdout.strip() else None


def _current_gh_login() -> str:
    global _cached_login
    if _cached_login is None:
        _cached_login = str(_gh_json(["api", "user", "-q", ".login"]) or "")
    return _cached_login


def _local_details_path():
    for candidate in (
        project_root.parent / "plugin-repo" / DEFAULT_PLUGIN_REPO["details_file"],
        project_root / "data" / DEFAULT_PLUGIN_REPO["details_file"],
    ):
        if candidate.is_file():
            return candidate
    return None


def _find_issue_number(plugin_id: str) -> int:
    path = _local_details_path()
    if path is None:
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    for entry in data if isinstance(data, list) else []:
        if str(entry.get("id", "")) == plugin_id:
            return int(entry.get("likeIssueNumber") or 0)
    return 0


def _reactions_url(issue_number: int) -> str:
    owner = DEFAULT_PLUGIN_REPO["owner"]
    repo = DEFAULT_PLUGIN_REPO["repo"]
    return "repos/{0}/{1}/issues/{2}/reactions".format(owner, repo, issue_number)


def _load_reaction_state(issue_number: int) -> Dict[str, Any]:
    reactions = _gh_json(["api", _reactions_url(issue_number)]) or []
    login = _current_gh_login()
    likes = sum(1 for r in reactions if r.get("content") == "+1")
    own_reaction_id = next(
        (r.get("id") for r in reactions
         if r.get("content") == "+1" and r.get("user", {}).get("login") == login),
        None,
    )
    return {"likes": likes, "downloads": 0, "liked": own_reaction_id is not None, "_reaction_id": own_reaction_id}


async def plugins_stats_proxy_summary(request: aiohttp.web.Request) -> aiohttp.web.Response:
    plugin_id = request.match_info.get("plugin_id", "")
    issue_number = _find_issue_number(plugin_id)
    if not issue_number:
        return aiohttp.web.json_response({"success": True, "stats": {"likes": 0, "downloads": 0, "liked": False}})
    try:
        state = _load_reaction_state(issue_number)
    except Exception as exc:
        logger.warning("读取插件点赞状态失败 plugin_id={} error={}", plugin_id, exc)
        return aiohttp.web.json_response({"success": False, "error": str(exc)}, status=502)
    state.pop("_reaction_id", None)
    return aiohttp.web.json_response({"success": True, "stats": state})


async def plugins_stats_proxy_toggle_like(request: aiohttp.web.Request) -> aiohttp.web.Response:
    plugin_id = request.match_info.get("plugin_id", "")
    issue_number = _find_issue_number(plugin_id)
    if not issue_number:
        return aiohttp.web.json_response({"success": False, "error": "no like-tracker issue for plugin"}, status=404)
    try:
        state = _load_reaction_state(issue_number)
        if state["liked"]:
            subprocess.run(
                ["gh", "api", "-X", "DELETE",
                 "{0}/{1}".format(_reactions_url(issue_number), state["_reaction_id"])],
                capture_output=True, text=True, timeout=_GH_TIMEOUT, check=True,
            )
        else:
            subprocess.run(
                ["gh", "api", "-X", "POST", _reactions_url(issue_number),
                 "-f", "content=+1"],
                capture_output=True, text=True, timeout=_GH_TIMEOUT, check=True,
            )
        new_state = _load_reaction_state(issue_number)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        logger.warning("切换插件点赞失败 plugin_id={} error={}", plugin_id, exc)
        return aiohttp.web.json_response({"success": False, "error": str(exc)}, status=502)
    new_state.pop("_reaction_id", None)
    return aiohttp.web.json_response({"success": True, "stats": new_state})
