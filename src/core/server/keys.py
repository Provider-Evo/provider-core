from __future__ import annotations

from typing import Any

from aiohttp.web_app import AppKey

REGISTRY_KEY: AppKey[Any] = AppKey("registry")
SESSION_KEY: AppKey[Any] = AppKey("session")

__all__ = ["REGISTRY_KEY", "SESSION_KEY"]
