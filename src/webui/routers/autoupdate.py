"""WebUI 自动更新控制 API 路由。"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiohttp.web

from src.core.config import get_config, reload_config
from src.logger import get_logger

logger = get_logger(__name__)

# 上次检查结果缓存
_last_check: Dict[str, Any] = {}


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent


def _get_autoupdate_config() -> Dict[str, Any]:
    cfg = get_config()
    au = cfg.autoupdate
    return {
        "enabled": au.enabled,
        "branch": au.branch,
        "interval": au.interval,
        "diff_update": au.diff_update,
        "mirrors": list(au.mirrors),
    }


async def _run_git(*args: str, timeout: int = 30) -> Tuple[bool, str, str]:
    root = _project_root()
    try:
        proc = await asyncio.create_subprocess_exec(
            "git", *args,
            cwd=str(root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        out = stdout.decode("utf-8", errors="replace").strip()
        err = stderr.decode("utf-8", errors="replace").strip()
        return proc.returncode == 0, out, err
    except asyncio.TimeoutError:
        return False, "", "git timeout"
    except FileNotFoundError:
        return False, "", "git not installed"
    except Exception as e:
        return False, "", str(e)


async def _fetch_from_mirrors(branch: str, mirrors: List[str]) -> Tuple[bool, str]:
    """按优先级尝试 fetch，返回 (成功, 使用的镜像源)。

    镜像源可以是完整 git remote URL，也可以是基础 URL（如 https://github.com/）。
    对于基础 URL，自动从当前 remote 提取仓库路径并拼接。
    """
    # 获取当前 remote URL 以提取仓库路径
    ok, current_url, _ = await _run_git("remote", "get-url", "origin")
    repo_path = ""
    if ok and current_url:
        # 提取仓库路径：https://github.com/user/repo.git -> user/repo.git
        # 或 git@github.com:user/repo.git -> user/repo.git
        for prefix in ["https://", "http://", "git://"]:
            if current_url.startswith(prefix):
                current_url = current_url[len(prefix):]
                # Remove host part
                if "/" in current_url:
                    current_url = current_url[current_url.index("/") + 1:]
                break
        else:
            # SSH format: git@host:user/repo.git
            if ":" in current_url:
                current_url = current_url[current_url.index(":") + 1:]
        repo_path = current_url

    for mirror in mirrors:
        # 如果是基础 URL（以 / 结尾），拼接仓库路径
        full_url = mirror
        if mirror.endswith("/") and repo_path:
            full_url = mirror + repo_path

        # 设置临时 remote URL
        ok, _, _ = await _run_git("remote", "set-url", "origin", full_url)
        if not ok:
            continue
        ok, _, err = await _run_git("fetch", "origin", branch, timeout=60)
        if ok:
            return True, mirror
        logger.debug("fetch from %s failed: %s", full_url, err)
    return False, ""


async def _get_changed_files(branch: str) -> Tuple[Optional[str], Optional[str], List[str]]:
    """获取变更文件列表。返回 (local_hash, remote_hash, changed_files)。"""
    ok, local_hash, _ = await _run_git("rev-parse", "HEAD")
    if not ok:
        return None, None, []
    ok, remote_hash, _ = await _run_git("rev-parse", "origin/{}".format(branch))
    if not ok:
        return local_hash, None, []
    if local_hash == remote_hash:
        return local_hash, remote_hash, []
    ok, diff_out, _ = await _run_git(
        "diff", "--name-only", "HEAD..origin/{}".format(branch)
    )
    files = [f for f in diff_out.splitlines() if f.strip()] if ok else []
    return local_hash, remote_hash, files


# =========================================================================
# API handlers
# =========================================================================

async def autoupdate_get(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/admin/autoupdate — 获取配置 + 上次检查结果。"""
    try:
        data = _get_autoupdate_config()
        data["last_check"] = _last_check
        return aiohttp.web.json_response({"success": True, "data": data})
    except Exception as e:
        return aiohttp.web.json_response({"success": False, "error": str(e)}, status=500)


async def autoupdate_put(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """PUT /v1/admin/autoupdate — 保存配置。"""
    try:
        body = await request.json()
        import tomlkit

        config_path = _project_root() / "config.toml"
        if not config_path.exists():
            return aiohttp.web.json_response({"success": False, "error": "config.toml not found"}, status=404)

        with open(str(config_path), "r", encoding="utf-8") as f:
            doc = tomlkit.load(f)

        if "autoupdate" not in doc:
            doc["autoupdate"] = tomlkit.table()

        au = doc["autoupdate"]
        if "enabled" in body:
            au["enabled"] = bool(body["enabled"])
        if "branch" in body:
            au["branch"] = str(body["branch"])
        if "interval" in body:
            au["interval"] = int(body["interval"])
        if "diff_update" in body:
            au["diff_update"] = bool(body["diff_update"])
        if "mirrors" in body:
            au["mirrors"] = [str(m) for m in body["mirrors"]]

        with open(str(config_path), "w", encoding="utf-8") as f:
            tomlkit.dump(doc, f)

        await reload_config()
        data = _get_autoupdate_config()
        return aiohttp.web.json_response({"success": True, "data": data})
    except Exception as e:
        return aiohttp.web.json_response({"success": False, "error": str(e)}, status=500)


async def autoupdate_check(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/admin/autoupdate/check — 检查更新，返回变更文件列表。"""
    global _last_check
    try:
        cfg = get_config().autoupdate
        branch = cfg.branch
        mirrors = list(cfg.mirrors) if cfg.mirrors else ["https://github.com/nichengfuben/provider-v2.git"]

        # Fetch from mirrors
        fetch_ok, used_mirror = await _fetch_from_mirrors(branch, mirrors)
        if not fetch_ok:
            _last_check = {"status": "error", "message": "All mirrors failed"}
            return aiohttp.web.json_response({"success": False, "error": "All mirrors failed"})

        local_hash, remote_hash, changed_files = await _get_changed_files(branch)

        _last_check = {
            "status": "ok",
            "mirror": used_mirror,
            "local_hash": (local_hash or "")[:8],
            "remote_hash": (remote_hash or "")[:8],
            "has_update": local_hash != remote_hash,
            "changed_files": changed_files,
            "changed_count": len(changed_files),
        }

        return aiohttp.web.json_response({"success": True, "data": _last_check})
    except Exception as e:
        _last_check = {"status": "error", "message": str(e)}
        return aiohttp.web.json_response({"success": False, "error": str(e)}, status=500)


async def autoupdate_diff(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/admin/autoupdate/diff — 返回单个文件的 diff。"""
    try:
        body = await request.json()
        filepath = body.get("file", "")
        if not filepath or ".." in filepath or filepath.startswith("/"):
            return aiohttp.web.json_response({"success": False, "error": "Invalid file path"}, status=400)

        cfg = get_config().autoupdate
        branch = cfg.branch
        ok, diff_out, err = await _run_git(
            "diff", "HEAD..origin/{}".format(branch), "--", filepath, timeout=30
        )
        if not ok:
            return aiohttp.web.json_response({"success": False, "error": err})
        return aiohttp.web.json_response({"success": True, "diff": diff_out, "file": filepath})
    except Exception as e:
        return aiohttp.web.json_response({"success": False, "error": str(e)}, status=500)


async def autoupdate_apply(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/admin/autoupdate/apply — 应用更新（差异或全量）。

    可选 body: {"files": ["file1.py", "file2.py"]} 仅更新指定文件。
    """
    try:
        body = {}
        try:
            body = await request.json()
        except Exception:
            pass

        cfg = get_config().autoupdate
        branch = cfg.branch
        selected_files = body.get("files")  # None = all files

        if cfg.diff_update and _last_check.get("changed_files"):
            # 差异更新：仅 checkout 选中的变更文件
            files = selected_files if selected_files is not None else _last_check["changed_files"]
            if not files:
                return aiohttp.web.json_response({"success": False, "error": "No files selected"})
            ok, out, err = await _run_git(
                "checkout", "origin/{}".format(branch), "--", *files, timeout=60
            )
            if not ok:
                return aiohttp.web.json_response({"success": False, "error": "git checkout failed: " + err})
            _last_check["applied"] = "diff"
            _last_check["applied_files"] = files
            logger.info("差异更新完成: %d 个文件", len(files))
        else:
            # 全量更新
            ok, out, err = await _run_git("pull", "origin", branch, timeout=120)
            if not ok:
                return aiohttp.web.json_response({"success": False, "error": "git pull failed: " + err})
            _last_check["applied"] = "full"
            logger.info("全量更新完成")

        return aiohttp.web.json_response({
            "success": True,
            "message": "Update applied. Restart to take effect.",
            "data": _last_check,
        })
    except Exception as e:
        return aiohttp.web.json_response({"success": False, "error": str(e)}, status=500)
