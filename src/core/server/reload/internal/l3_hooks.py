from __future__ import annotations

"""L3 热重载 prepare 阶段钩子注册表。"""

from typing import Callable, Dict, Tuple

from src.foundation.logger import get_logger

__all__ = [
    "register_l3_prepare_hook",
    "clear_l3_prepare_hooks",
    "list_l3_prepare_hooks",
    "run_l3_prepare_hooks",
]

logger = get_logger(__name__)

_hooks: Dict[str, Callable[[], None]] = {}


def register_l3_prepare_hook(name: str, hook: Callable[[], None]) -> None:
    _hooks[name] = hook


def clear_l3_prepare_hooks() -> None:
    _hooks.clear()


def list_l3_prepare_hooks() -> Tuple[str, ...]:
    return tuple(_hooks.keys())


def run_l3_prepare_hooks() -> None:
    for name, hook in list(_hooks.items()):
        try:
            hook()
        except Exception as exc:
            logger.warning("L3 prepare hook %s failed: %s", name, exc)
