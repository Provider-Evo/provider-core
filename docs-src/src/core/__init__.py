from __future__ import annotations

"""Core infrastructure package (core).

Public API re-exports for convenience. Prefer direct submodule imports
for new code (e.g. ``from src.core.dispatch.registry import Registry``).
"""

from src.core.config import get_config, start_config_watcher
from src.core.dispatch import candidate, gateway, registry, selector
from src.core.dispatch.candidate import Candidate
from src.core.dispatch.gateway import dispatch
from src.core.dispatch.registry import Registry
from src.core.dispatch.selector import Selector
from src.core.server import FileWatcher, create_app

__all__ = [
    "get_config",
    "start_config_watcher",
    "candidate",
    "gateway",
    "registry",
    "selector",
    "Candidate",
    "dispatch",
    "Registry",
    "Selector",
    "FileWatcher",
    "create_app",
]