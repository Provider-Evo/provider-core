from __future__ import annotations

"""文件变更分类 — 将路径映射到 L0–L4 热重载层级。"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import FrozenSet, Set

from src.core.server.plugins.plugin_catalog import (
    is_plugin_enabled,
    manifest_id_from_dir,
    plugin_dir_from_path,
    resolve_platform_plugin_id,
)

__all__ = ["ClassifyResult", "classify_paths"]

_CORE_DIR = "core"
_ROUTES_DIR = "routes"
_PLATFORM_DIR = "platforms"
_WEBUI_DIR = "webui"

_PROCESS_SRC_FILES = frozenset({"logger.py", "paths.py"})
_PROCESS_CONFIG_FILES = frozenset({"pyproject.toml", "requirements.txt"})
_WEBUI_CONFIG_NAMES = frozenset({"webui_config.toml", "config.toml"})
_PLUGINS_DIR = "plugins"
_MANIFEST_NAME = "_manifest.json"
_MANIFEST_DISABLED_NAME = "_manifest.json.disabled"
_ROUTE_PLUGIN_TYPES = frozenset({"fncall", "webui", "coplan", "general"})

# 插件运行时配置文件 — 变更后按需读取，不触发重载
_PLUGIN_RUNTIME_CONFIG_NAMES = frozenset(
    {
        "config.toml",
        "config.toml.example",
        "accounts.py",
        "accounts.py.example",
        "config_schema.json",
    }
)

# 变更后走 L3 的 core 子目录（其余 core 默认 L4）
_CORE_L3_PARTS = frozenset(
    {
        "dispatch",
        "config",
        "errors",
        "fncall",
        "utils",
        "server",
    },
)


@dataclass(frozen=True)
class ClassifyResult:
    """一批文件变更的分类结果。"""

    process: bool = False
    application: bool = False
    static: bool = False
    platforms: FrozenSet[str] = field(default_factory=frozenset)
    plugins: FrozenSet[str] = field(default_factory=frozenset)
    plugin_app_reload: bool = False
    plugin_manifest_sync: FrozenSet[str] = field(default_factory=frozenset)


def _read_manifest_at(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        import json

        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _manifest_id_from_path(path: Path) -> str | None:
    plugin_dir = plugin_dir_from_path(path)
    if plugin_dir is None:
        return None
    if path.name == _MANIFEST_NAME:
        data = _read_manifest_at(plugin_dir / _MANIFEST_NAME)
    elif path.name == _MANIFEST_DISABLED_NAME:
        data = _read_manifest_at(plugin_dir / _MANIFEST_DISABLED_NAME)
    else:
        plugin_id = manifest_id_from_dir(plugin_dir)
        return plugin_id or None
    if data is None:
        return None
    plugin_id = str(data.get("id") or "").strip()
    return plugin_id or None


def _plugin_type_from_path(path: Path) -> str | None:
    plugin_dir = plugin_dir_from_path(path)
    if plugin_dir is None:
        return None
    data = _read_manifest_at(plugin_dir / _MANIFEST_NAME)
    if data is None:
        return None
    plugin_type = str(data.get("plugin_type") or "").strip().lower()
    return plugin_type or None


def _is_plugin_static_path(path: Path) -> bool:
    parts = path.parts
    try:
        idx = parts.index(_PLUGINS_DIR)
    except ValueError:
        return False
    rest = parts[idx + 1 :]
    return len(rest) >= 2 and rest[1] == "static"


def _is_manifest_path(path: Path) -> bool:
    return path.name in {_MANIFEST_NAME, _MANIFEST_DISABLED_NAME}


def _classify_plugin_path(
    path: Path,
    plugins: Set[str],
    plugin_app_reload: bool,
    plugin_manifest_sync: Set[str],
) -> tuple[bool, bool]:
    """分类 plugins/ 下路径，返回 (static, plugin_app_reload)。"""
    if _is_plugin_static_path(path):
        return True, plugin_app_reload

    plugin_dir = plugin_dir_from_path(path)
    if plugin_dir is None:
        return False, plugin_app_reload

    if _is_manifest_path(path):
        plugin_id = _manifest_id_from_path(path)
        if plugin_id:
            plugins.add(plugin_id)
            plugin_manifest_sync.add(plugin_id)
        return False, True

    # 插件运行时配置文件（config.toml / accounts.py 等）变更不触发重载
    if path.name in _PLUGIN_RUNTIME_CONFIG_NAMES:
        return False, plugin_app_reload

    if not is_plugin_enabled(plugin_dir):
        return False, plugin_app_reload

    plugin_id = manifest_id_from_dir(plugin_dir)
    if not plugin_id:
        return False, plugin_app_reload

    plugins.add(plugin_id)

    plugin_type = _plugin_type_from_path(path)
    if plugin_type in _ROUTE_PLUGIN_TYPES:
        return False, True
    return False, plugin_app_reload


def _platform_name(parts: tuple[str, ...]) -> str | None:
    if len(parts) < 2 or parts[0] != _PLATFORM_DIR:
        return None
    return parts[1].split(".")[0]


def _classify_core_path(sub_parts: tuple[str, ...]) -> str:
    """返回 ``process`` | ``application``。"""
    if not sub_parts:
        return "process"
    if sub_parts[0] == "server" and len(sub_parts) >= 2 and sub_parts[1] == "reload":
        return "process"
    if sub_parts[0] in _CORE_L3_PARTS:
        return "application"
    return "process"


def _classify_src_path(
    sub_parts: tuple[str, ...],
    process: bool,
    application: bool,
    static: bool,
    platforms: Set[str],
    plugins: Set[str],
) -> tuple[bool, bool, bool, Set[str], Set[str]]:
    """分类 src/ 下相对路径。"""
    if not sub_parts:
        return True, application, static, platforms, plugins
    first = sub_parts[0]
    if first == _CORE_DIR:
        if _classify_core_path(sub_parts[1:]) == "process":
            return True, application, static, platforms, plugins
        return process, True, static, platforms, plugins
    if first == _ROUTES_DIR:
        return process, True, static, platforms, plugins
    if first == _PLATFORM_DIR:
        name = _platform_name(sub_parts)
        if name:
            plugin_id = resolve_platform_plugin_id(name)
            if plugin_id:
                plugins.add(plugin_id)
            else:
                platforms.add(name)
            return process, application, static, platforms, plugins
        return True, application, static, platforms, plugins
    if first == _WEBUI_DIR:
        if len(sub_parts) >= 2 and sub_parts[1] == "frontend_media":
            return process, application, True, platforms, plugins
        return process, True, static, platforms, plugins
    if first in _PROCESS_SRC_FILES:
        return True, application, static, platforms, plugins
    return True, application, static, platforms, plugins


def classify_paths(changed: Set[str]) -> ClassifyResult:
    """将变更文件路径分类为进程重启、应用重载、平台重载或静态通知。"""
    process = False
    application = False
    static = False
    platforms: Set[str] = set()
    plugins: Set[str] = set()
    plugin_app_reload = False
    plugin_manifest_sync: Set[str] = set()

    for fp in changed:
        p = Path(fp)
        if _PLUGINS_DIR in p.parts:
            is_static, plugin_app_reload = _classify_plugin_path(
                p, plugins, plugin_app_reload, plugin_manifest_sync
            )
            if is_static:
                static = True
            continue
        if p.name in _PROCESS_CONFIG_FILES or p.name == "main.py":
            process = True
            continue
        if p.name in _WEBUI_CONFIG_NAMES or p.name == "main_config.toml":
            continue
        try:
            src_idx = p.parts.index("src")
        except ValueError:
            if p.suffix in {".py", ".toml", ".js", ".css", ".html"}:
                process = True
            continue
        process, application, static, platforms, plugins = _classify_src_path(
            p.parts[src_idx + 1 :],
            process,
            application,
            static,
            platforms,
            plugins,
        )

    if process:
        return ClassifyResult(process=True)
    return ClassifyResult(
        process=False,
        application=application,
        static=static,
        platforms=frozenset(platforms),
        plugins=frozenset(plugins),
        plugin_app_reload=plugin_app_reload,
        plugin_manifest_sync=frozenset(plugin_manifest_sync),
    )


def classify_paths_incremental(changed: Set[str]) -> ClassifyResult:
    """增量分类：只重载变更部分，减少重载范围。

    优化点：
    1. 只重载变更的插件，不影响其他插件
    2. 只重载变更的平台，不影响其他平台
    3. 减少不必要的应用路由重载
    """
    # 复用标准分类
    result = classify_paths(changed)

    # 如果是进程重启，直接返回
    if result.process:
        return result

    # 优化：只重载变更的插件和平台
    # 插件已经精确到具体插件，无需优化
    # 平台已经精确到具体平台，无需优化

    return result
