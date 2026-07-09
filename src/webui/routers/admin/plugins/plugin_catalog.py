"""插件市场与 catalog API。"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import aiohttp.web

from src.core.config import get_config
from src.webui.routers.admin.plugins.runtime.mirrors import resolve_fetch_urls
from src.webui.routers.admin.plugins.plugin_support import (
    DEFAULT_PLUGIN_REPO,
    find_plugin_path_by_id,
    read_manifest,
)

__all__ = [
    "plugins_fetch_raw",
    "plugins_git_status",
    "plugins_host_version",
    "plugins_icon",
    "plugins_local_changelog",
    "plugins_local_readme",
    "plugins_market_config",
]

def _parse_host_version(version: str) -> Dict[str, int]:
    parts = (version or "0.0.0").strip().split("-")[0].split(".")
    nums = [int(p) if p.isdigit() else 0 for p in parts[:3]]
    while len(nums) < 3:
        nums.append(0)
    return {"version_major": nums[0], "version_minor": nums[1], "version_patch": nums[2]}


async def plugins_host_version(_request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/admin/plugins/version — 宿主版本（兼容检查）。"""
    cfg = get_config()
    version = str(cfg.server.version or "0.0.0")
    parsed = _parse_host_version(version)
    return aiohttp.web.json_response({"version": version, **parsed})


async def plugins_git_status(_request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/admin/plugins/git-status — 检测本机 git。"""
    git = shutil.which("git")
    if not git:
        return aiohttp.web.json_response({"installed": False, "error": "git not found"})
    try:
        proc = subprocess.run(
            [git, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if proc.returncode != 0:
            return aiohttp.web.json_response(
                {"installed": False, "error": proc.stderr.strip() or "git --version failed"},
            )
        return aiohttp.web.json_response(
            {"installed": True, "version": proc.stdout.strip()},
        )
    except Exception as exc:
        return aiohttp.web.json_response({"installed": False, "error": str(exc)})


async def plugins_market_config(_request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/admin/plugins/market-config — 默认 plugin-repo 源。"""
    payload = dict(DEFAULT_PLUGIN_REPO)
    payload["success"] = True
    return aiohttp.web.json_response(payload)


async def plugins_fetch_raw(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/admin/plugins/fetch-raw — 代理拉取 GitHub raw 文件。"""
    try:
        body = await request.json()
    except Exception:
        return aiohttp.web.json_response({"success": False, "error": "invalid json"}, status=400)

    owner = str(body.get("owner") or DEFAULT_PLUGIN_REPO["owner"]).strip()
    repo = str(body.get("repo") or DEFAULT_PLUGIN_REPO["repo"]).strip()
    branch = str(body.get("branch") or DEFAULT_PLUGIN_REPO["branch"]).strip()
    file_path = str(body.get("file_path") or DEFAULT_PLUGIN_REPO["details_file"]).strip()

    if not owner or not repo or not file_path or ".." in file_path:
        return aiohttp.web.json_response({"success": False, "error": "invalid parameters"}, status=400)

    urls = resolve_fetch_urls(owner, repo, branch, file_path)
    last_error = ""
    for url in urls:
        try:
            req = Request(url, headers={"User-Agent": "provider-v2-webui"})
            with urlopen(req, timeout=20) as resp:
                data = resp.read().decode("utf-8", errors="replace")
            return aiohttp.web.json_response({"success": True, "data": data, "url": url})
        except HTTPError as exc:
            last_error = f"HTTP {exc.code}"
        except URLError as exc:
            last_error = str(exc.reason)
        except Exception as exc:
            last_error = str(exc)
    return aiohttp.web.json_response(
        {"success": False, "error": last_error or "all mirrors failed", "url": urls[-1] if urls else ""},
        status=502,
    )


async def plugins_local_readme(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/admin/plugins/local-readme/{plugin_id}"""
    from src.webui.routers.admin.plugins.plugin_support import read_plugin_readme

    plugin_id = request.match_info.get("plugin_id", "")
    plugin_path = find_plugin_path_by_id(plugin_id)
    if plugin_path is None:
        return aiohttp.web.json_response({"success": False, "error": "plugin not installed"})
    readme = read_plugin_readme(plugin_path)
    if not readme:
        return aiohttp.web.json_response({"success": False, "error": "README not found"})
    return aiohttp.web.json_response({"success": True, "data": readme})


async def plugins_local_changelog(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/admin/plugins/local-changelog/{plugin_id}"""
    from src.webui.routers.admin.plugins.plugin_support import read_plugin_changelog

    plugin_id = request.match_info.get("plugin_id", "")
    plugin_path = find_plugin_path_by_id(plugin_id)
    if plugin_path is None:
        return aiohttp.web.json_response({"success": False, "error": "plugin not installed"})
    changelog = read_plugin_changelog(plugin_path)
    return aiohttp.web.json_response({"success": True, "data": changelog or ""})


def _find_plugin_icon(plugin_path: Path) -> Optional[Path]:
    for name in ("icon.png", "icon.svg", "icon.webp", "icon.jpg", "icon.jpeg"):
        candidate = plugin_path / name
        if candidate.is_file():
            return candidate
    display = read_manifest_icon_path(plugin_path)
    if display:
        candidate = plugin_path / display
        if candidate.is_file():
            return candidate
    return None


def read_manifest_icon_path(plugin_path: Path) -> str:
    from src.webui.routers.admin.plugins.plugin_support import read_manifest

    manifest = read_manifest(plugin_path)
    display = manifest.get("display") or {}
    if isinstance(display, dict):
        icon = display.get("icon") or {}
        if isinstance(icon, dict) and icon.get("type") == "local":
            value = str(icon.get("value") or "").strip().replace("\\", "/")
            if value and ".." not in value:
                return value
    return ""


async def plugins_icon(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/admin/plugins/icon/{plugin_id} — 返回插件本地图标。"""
    plugin_id = request.match_info.get("plugin_id", "")
    plugin_path = find_plugin_path_by_id(plugin_id)
    if plugin_path is None:
        raise aiohttp.web.HTTPNotFound()

    icon_path = _find_plugin_icon(plugin_path)
    if icon_path is None:
        raise aiohttp.web.HTTPNotFound()

    suffix = icon_path.suffix.lower()
    content_type = {
        ".png": "image/png",
        ".svg": "image/svg+xml",
        ".webp": "image/webp",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }.get(suffix, "application/octet-stream")
    return aiohttp.web.FileResponse(
        path=icon_path,
        headers={"Content-Type": content_type, "Cache-Control": "public, max-age=3600"},
    )
