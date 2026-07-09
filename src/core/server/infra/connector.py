"""Shared aiohttp TCPConnector factory with configurable connection pool.

Centralizes connector creation so that all components (Worker, adapters,
proxy manager) share a single, consistently configured connector instance.
"""

from __future__ import annotations

import ssl
from typing import Optional

import aiohttp

from src.core.config import get_config

__all__ = ["make_connector"]

# Module-level cache so multiple calls within the same process return the
# same connector (avoids accidental duplicate pools).
_connector: Optional[aiohttp.TCPConnector] = None


def make_connector() -> aiohttp.TCPConnector:
    """中文说明：make_connector。

Create or return a cached ``aiohttp.TCPConnector`` from config.

Reads ``[http_pool]`` section of ``config/main_config.toml``.

Returns:
    Shared TCPConnector instance."""
    global _connector
    if _connector is not None and not _connector.closed:
        return _connector

    cfg = get_config()
    pool = cfg.http_pool

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    _connector = aiohttp.TCPConnector(
        ssl=ctx,
        limit=pool.limit,
        limit_per_host=pool.limit_per_host,
        keepalive_timeout=pool.keepalive_timeout,
        force_close=False,
        enable_cleanup_closed=True,
    )
    return _connector
