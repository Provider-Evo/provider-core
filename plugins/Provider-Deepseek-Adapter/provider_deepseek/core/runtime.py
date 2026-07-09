from __future__ import annotations

"""Standalone runtime shims when host project modules are absent."""


def get_proxy_server() -> str:
    """Return an empty proxy URL in standalone mode."""
    return ""
