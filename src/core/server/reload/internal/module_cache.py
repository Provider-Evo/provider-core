from __future__ import annotations

"""L3 模块缓存失效：按变更路径收集并清除 sys.modules 条目。"""

import sys
from pathlib import Path
from typing import AbstractSet, Iterable, Set

from src.foundation.logger import get_logger
from src.foundation.paths import project_root

__all__ = [
    "path_to_src_module",
    "collect_modules_for_paths",
    "invalidate_modules_for_paths",
    "invalidate_application_layers",
]

logger = get_logger(__name__)

_WIRING_MODULES = frozenset({"src.bootstrap.app_factory"})

_LAYER_PREFIXES = ("src.routes.", "src.webui.", "src.bootstrap.")


def path_to_src_module(path: Path | str, *, root: Path | None = None) -> str:
    root_path = Path(root or project_root).resolve()
    file_path = Path(path).resolve()
    try:
        rel = file_path.relative_to(root_path)
    except ValueError:
        return ""
    parts = list(rel.parts)
    if not parts or parts[0] != "src":
        return ""
    if parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]
    elif parts[-1] == "__init__.py":
        parts.pop()
    return ".".join(parts)


def _parent_modules(module: str) -> Iterable[str]:
    bits = module.split(".")
    for i in range(len(bits) - 1, 1, -1):
        yield ".".join(bits[:i])


def collect_modules_for_paths(
    paths: AbstractSet[str],
    *,
    root: Path | None = None,
) -> Set[str]:
    modules: Set[str] = set()
    for raw in paths:
        module = path_to_src_module(raw, root=root)
        if not module:
            continue
        modules.add(module)
        modules.update(_parent_modules(module))
        if module.startswith("src.webui."):
            modules.update(_WIRING_MODULES)
    return modules


def invalidate_modules_for_paths(
    paths: AbstractSet[str],
    *,
    root: Path | None = None,
) -> Set[str]:
    targets = collect_modules_for_paths(paths, root=root)
    removed: Set[str] = set()
    for name in sorted(targets, key=len, reverse=True):
        if name in sys.modules:
            sys.modules.pop(name, None)
            removed.add(name)
    return removed


def invalidate_application_layers() -> Set[str]:
    removed: Set[str] = set()
    for name in list(sys.modules):
        if any(name.startswith(prefix) for prefix in _LAYER_PREFIXES):
            sys.modules.pop(name, None)
            removed.add(name)
    return removed
