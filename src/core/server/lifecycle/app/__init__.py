from __future__ import annotations

"""应用创建与 AppHost 生命周期。"""

from src.core.server.lifecycle.app.app import REGISTRY_KEY, SESSION_KEY, create_app
from src.core.server.lifecycle.app.app_host import AppHost

__all__ = ["REGISTRY_KEY", "SESSION_KEY", "AppHost", "create_app"]
