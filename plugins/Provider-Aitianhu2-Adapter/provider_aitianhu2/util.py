from __future__ import annotations

"""AItianhu2 对外工具门面。"""

from typing import Any

from .core.constants import CAPS, MODELS

__all__ = [
    "Adapter",
    "Aitianhu2Adapter",
    "MODELS",
    "CAPS",
]


def __getattr__(name: str) -> Any:
    """懒加载 Adapter / Aitianhu2Adapter，避免顶层 import 触发 core 全量加载。"""
    if name in {"Adapter", "Aitianhu2Adapter"}:
        from .core.adaptercore import Adapter as _Adapter  # noqa: PLC0415

        return _Adapter
    raise AttributeError(
        "module 'src.platforms.aitianhu2.util' has no attribute {!r}".format(name)
    )
