"""Proxy selector re-export from echotools.

Canonical implementation lives in ``echotools.dispatch.proxy_selector``.
This module exists solely for backward-compatible import paths.
"""
from echotools.dispatch.proxy_selector import ProxyRecord, ProxySelector  # noqa: F401

__all__ = ["ProxySelector", "ProxyRecord"]
