from __future__ import annotations

"""L3 Python 模块失效编排。"""

from typing import AbstractSet, Optional, Set

from .l3_hooks import run_l3_prepare_hooks
from .module_cache import (
    invalidate_application_layers,
    invalidate_modules_for_paths,
)

__all__ = ["prepare_python_reload"]


def prepare_python_reload(
    paths: Optional[AbstractSet[str]],
) -> Set[str]:
    run_l3_prepare_hooks()
    if paths:
        return invalidate_modules_for_paths(paths)
    return invalidate_application_layers()
