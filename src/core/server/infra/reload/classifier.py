from __future__ import annotations

"""文件变更分类 — 将路径映射到 L0–L4 热重载层级。"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import FrozenSet, Set

__all__ = ["ClassifyResult", "classify_paths"]

_CORE_DIR = "core"
_ROUTES_DIR = "routes"
_PLATFORM_DIR = "platforms"
_WEBUI_DIR = "webui"

_PROCESS_SRC_FILES = frozenset({"logger.py", "paths.py"})
_PROCESS_CONFIG_FILES = frozenset({"pyproject.toml", "requirements.txt"})
_WEBUI_CONFIG_NAMES = frozenset({"webui_config.toml", "config.toml"})
# WebUI 配置由 API 按需读取，变更不触发任何热重载层级。

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


def _platform_name(parts: tuple[str, ...]) -> str | None:
    if len(parts) < 2 or parts[0] != _PLATFORM_DIR:
        return None
    return parts[1].split(".")[0]


def _classify_core_path(sub_parts: tuple[str, ...]) -> str:
    """返回 ``process`` | ``application``。"""
    if not sub_parts:
        return "process"
    if sub_parts[0] == "server" and len(sub_parts) >= 3 and sub_parts[1] == "infra":
        if sub_parts[2] == "reload":
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
) -> tuple[bool, bool, bool, Set[str]]:
    """分类 src/ 下相对路径，返回更新后的四元组。"""
    if not sub_parts:
        return True, application, static, platforms
    first = sub_parts[0]
    if first == _CORE_DIR:
        if _classify_core_path(sub_parts[1:]) == "process":
            return True, application, static, platforms
        return process, True, static, platforms
    if first == _ROUTES_DIR:
        return process, True, static, platforms
    if first == _PLATFORM_DIR:
        name = _platform_name(sub_parts)
        if name:
            platforms.add(name)
            return process, application, static, platforms
        return True, application, static, platforms
    if first == _WEBUI_DIR:
        if len(sub_parts) >= 2 and sub_parts[1] == "static":
            return process, application, True, platforms
        return process, True, static, platforms
    if first in _PROCESS_SRC_FILES:
        return True, application, static, platforms
    return True, application, static, platforms


def classify_paths(changed: Set[str]) -> ClassifyResult:
    """将变更文件路径分类为进程重启、应用重载、平台重载或静态通知。"""
    process = False
    application = False
    static = False
    platforms: Set[str] = set()

    for fp in changed:
        p = Path(fp)
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
        process, application, static, platforms = _classify_src_path(
            p.parts[src_idx + 1:], process, application, static, platforms
        )

    if process:
        return ClassifyResult(process=True)
    return ClassifyResult(
        process=False,
        application=application,
        static=static,
        platforms=frozenset(platforms),
    )
