from __future__ import annotations

"""Core infrastructure package (core).

Public API re-exports for convenience. Prefer direct submodule imports
for new code (e.g. ``from src.core.dispatch.engine.registry import Registry``).
"""

from src.foundation.config import get_config, start_config_watcher
from src.core.dispatch.cand import Candidate
from src.core.dispatch.engine import gateway
from src.core.dispatch.engine.gateway import dispatch
from src.core.dispatch.engine.registry import Registry
from src.core.dispatch.engine.selector import Selector
from src.core.server import FileWatcher, create_app

__all__ = [
    "get_config",
    "start_config_watcher",
    "Candidate",
    "dispatch",
    "gateway",
    "Registry",
    "Selector",
    "FileWatcher",
    "create_app",
]
