from __future__ import annotations

"""调度子系统：候选、网关、注册表、选择器。"""

from src.core.dispatch.engine.gateway import dispatch
from src.core.dispatch.engine.registry import Registry
from src.core.dispatch.engine.selector import Selector

__all__ = [
    "dispatch",
    "Registry",
    "Selector",
]
