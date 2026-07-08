from __future__ import annotations

"""Server subsystem — app creation, HTTP utils, proxy management, file watching, auto-update.

Re-exports from submodules for backward compatibility:

.. code-block:: python

    # New path (recommended)
    from src.core.server import create_app, FileWatcher, activate, AutoUpdater
"""

from typing import Any

from aiohttp.web_app import AppKey

from echotools.lifecycle.updater import AutoUpdater
from echotools.lifecycle.updater import get_updater, set_updater
from echotools.process.port import *  # noqa: F401, F403
from echotools.web.utils import json_response

from src.core.server.app import REGISTRY_KEY, SESSION_KEY, create_app
from src.core.server.http_utils import clean_fncall, get_json, safe_flush
from src.core.server.proxy import (
    activate,
    deactivate,
    get_proxy_dict,
    get_proxy_server,
    is_active,
)
from src.core.server.watcher import FileWatcher

__all__ = [
    # --- autoupdate ---
    "AutoUpdater",
    "get_updater",
    "set_updater",
    # --- http ---
    "clean_fncall",
    "safe_flush",
    "get_json",
    # --- proxy ---
    "activate",
    "deactivate",
    "is_active",
    "get_proxy_server",
    "get_proxy_dict",
    # --- server ---
    "create_app",
    "json_response",
    "REGISTRY_KEY",
    "SESSION_KEY",
    # --- watcher ---
    "FileWatcher",
]
