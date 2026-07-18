"""plugin_support 模块 — WebUI 层。

职责：
    作为 Provider-Evo 项目标准模块，提供 plugin_support 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""


from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp.web

from src.foundation.logger import get_logger
from src.foundation.paths import project_root

__all__ = [
    "DEFAULT_PLUGIN_REPO",
    "find_plugin_path_by_id",
    "iter_plugin_dirs",
    "plugins_root",
    "read_manifest",
    "read_plugin_changelog",
    "read_plugin_readme",
    "reload_plugins_from_request",
    "validate_plugin_id",
]

logger = get_logger(__name__)

DEFAULT_PLUGIN_REPO = {
    "owner": "Provider-Evo",
    "repo": "plugin-repo",
    "branch": "main",
    "details_file": "plugin_details.json",
    "fallback_owner": "nichengfuben",
}


def plugins_root() -> Path:
    return project_root / "plugins"


def iter_plugin_dirs() -> List[Path]:
    root = plugins_root()
    if not root.is_dir():
        return []
    out: List[Path] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if (child / "_manifest.json").is_file() or (child / "_manifest.json.disabled").is_file():
            out.append(child)
    return out


def read_manifest(plugin_dir: Path) -> Dict[str, Any]:
    for name in ("_manifest.json", "_manifest.json.disabled"):
        path = plugin_dir / name
        if path.is_file():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {}
    return {}


def validate_plugin_id(plugin_id: str) -> bool:
    if not plugin_id:
        return False
    if "/" in plugin_id or "\\" in plugin_id or ".." in plugin_id:
        return False
    if "\x00" in plugin_id:
        return False
    return True


def find_plugin_path_by_id(plugin_id: str) -> Optional[Path]:
    for plugin_dir in iter_plugin_dirs():
        manifest = read_manifest(plugin_dir)
        if manifest.get("id", "").lower() == plugin_id.lower():
            return plugin_dir
    return None


def read_plugin_readme(plugin_dir: Path) -> str:
    for name in ("README.md", "readme.md", "Readme.md"):
        path = plugin_dir / name
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="replace")
    return ""


def read_plugin_changelog(plugin_dir: Path) -> str:
    for name in ("CHANGELOG.md", "changelog.md", "Changelog.md"):
        path = plugin_dir / name
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="replace")
    manifest = read_manifest(plugin_dir)
    changelog = manifest.get("changelog")
    return str(changelog) if changelog else ""


async def reload_plugins_from_request(
    request: aiohttp.web.Request, *, reload_app: bool = True
) -> Dict[str, int]:
    """安装/启用变更后热重载插件与平台注册表。"""
    from src.core.server import REGISTRY_KEY, SESSION_KEY

    registry = request.app.get(REGISTRY_KEY)
    session = request.app.get(SESSION_KEY)
    if registry is None or session is None:
        logger.warning("插件热重载跳过：registry 或 session 不可用")
        return {"loaded": 0, "failed": 0, "inactive": 0}
    try:
        return await registry.reload_plugins(session, reload_app=reload_app)
    except Exception as exc:
        logger.error("插件热重载失败: %s", exc)
        return {"loaded": 0, "failed": 0, "inactive": 0}
