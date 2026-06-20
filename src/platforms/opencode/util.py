from __future__ import annotations

# src/platforms/opencode/util.py
"""Opencode public interface.

Exports shared constants/functions eagerly; lazy-loads the Adapter class
via module-level ``__getattr__``.
"""

from typing import Any

from src.platforms.opencode.core.constants import (
    BASE_URL,
    CAPS,
    CHAT_PATH,
    FETCH_MODELS_ENABLED,
    FILTER_PAID_MODELS,
    MODEL_FETCH_INTERVAL,
    MODELS,
    MODELS_PATH,
    PLATFORM_NAME,
    PROXY_REFRESH_INTERVAL,
    RATE_LIMIT_COOLDOWN,
    RECOVERY_INTERVAL,
)
from src.platforms.opencode.core.headers import build_headers
from src.platforms.opencode.core.payloads import build_payload
from src.platforms.opencode.core.sse import parse_sse_line


def __getattr__(name: str) -> Any:
    """Module-level lazy attribute for adapter class."""
    if name in ("OpencodeAdapter", "Adapter"):
        from src.platforms.opencode.core.adaptercore import (  # noqa: PLC0415
            OpencodeAdapter as _OpencodeAdapter,
        )

        return _OpencodeAdapter
    raise AttributeError(
        "module 'src.platforms.opencode.util' has no attribute '{}'".format(name)
    )


__all__ = [
    "OpencodeAdapter",
    "Adapter",
    "PLATFORM_NAME",
    "BASE_URL",
    "CHAT_PATH",
    "MODELS_PATH",
    "RATE_LIMIT_COOLDOWN",
    "RECOVERY_INTERVAL",
    "MODELS",
    "CAPS",
    "FETCH_MODELS_ENABLED",
    "MODEL_FETCH_INTERVAL",
    "FILTER_PAID_MODELS",
    "PROXY_REFRESH_INTERVAL",
    "build_headers",
    "build_payload",
    "parse_sse_line",
]
