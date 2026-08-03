"""插件目录查找与 manifest 解析。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

from src.foundation.paths import project_root

__all__ = [
    "find_plugin_dir_by_id",
    "is_plugin_enabled",
    "manifest_id_from_dir",
    "normalize_platform_name",
    "plugin_dir_from_path",
    "resolve_platform_plugin_id",
]

_MANIFEST_NAME = "_manifest.json"
_MANIFEST_DISABLED_NAME = "_manifest.json.disabled"
_PLUGINS_DIR = "plugins"
_PLATFORM_ALIASES = {
    "opencode": "zen",
    "opencodezen": "zen",
}


def normalize_platform_name(platform_name: str) -> str:
    """将 legacy 平台名映射为已注册的 ``PlatformAdapter.name``。"""
    raw = (platform_name or "").strip().lower()
    if not raw:
        return raw
    return _PLATFORM_ALIASES.get(raw, raw)


def _plugins_root() -> Path:
    return project_root / "plugins"


def _read_manifest_file(path: Path) -> Dict[str, object]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _read_manifest(plugin_dir: Path) -> Dict[str, object]:
    return _read_manifest_file(plugin_dir / _MANIFEST_NAME)


def _read_disabled_manifest(plugin_dir: Path) -> Dict[str, object]:
    return _read_manifest_file(plugin_dir / _MANIFEST_DISABLED_NAME)


def _platform_slug_from_dir(plugin_dir: Path) -> str:
    name = plugin_dir.name
    if name.startswith("Provider-") and name.endswith("-Adapter"):
        slug = name[len("Provider-") : -len("-Adapter")]
    else:
        slug = name
    return slug.lower().replace("-", "").replace("_", "")


def is_plugin_enabled(plugin_dir: Path) -> bool:
    """插件目录是否处于启用状态（存在 active manifest）。"""
    return (plugin_dir / _MANIFEST_NAME).is_file()


def manifest_id_from_dir(plugin_dir: Path) -> str:
    """读取插件 manifest id（优先 active，否则 disabled）。"""
    manifest = _read_manifest(plugin_dir)
    plugin_id = str(manifest.get("id", "")).strip()
    if plugin_id:
        return plugin_id
    disabled = _read_disabled_manifest(plugin_dir)
    return str(disabled.get("id", "")).strip()


def plugin_dir_from_path(path: Path) -> Optional[Path]:
    """从任意路径解析 ``plugins/<plugin_dir>``。"""
    parts = path.parts
    try:
        idx = parts.index(_PLUGINS_DIR)
    except ValueError:
        return None
    if len(parts) <= idx + 1:
        return None
    return Path(*parts[: idx + 2])


def find_plugin_dir_by_id(plugin_id: str) -> Optional[Path]:
    """按 manifest id 查找插件目录。"""
    target = (plugin_id or "").strip().lower()
    if not target:
        return None
    root = _plugins_root()
    if not root.is_dir():
        return None
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if (
            not manifest_id_from_dir(child)
            and not (child / _MANIFEST_DISABLED_NAME).is_file()
        ):
            continue
        current = manifest_id_from_dir(child).strip().lower()
        if current == target:
            return child
    return None


@lru_cache(maxsize=1)
def _platform_plugin_index() -> Dict[str, str]:
    index: Dict[str, str] = {}
    root = _plugins_root()
    if not root.is_dir():
        return index
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if not is_plugin_enabled(child):
            continue
        manifest = _read_manifest(child)
        if str(manifest.get("plugin_type", "")).strip().lower() != "platform":
            continue
        plugin_id = str(manifest.get("id", "")).strip()
        if not plugin_id:
            continue
        slug = _platform_slug_from_dir(child)
        index[slug] = plugin_id
    return index


def resolve_platform_plugin_id(platform_name: str) -> Optional[str]:
    """将 legacy 平台目录名或 adapter.name 映射到插件 manifest id。"""
    raw = (platform_name or "").strip().lower()
    if not raw:
        return None
    normalized = normalize_platform_name(raw).replace("_", "").replace("-", "")
    return _platform_plugin_index().get(normalized)
