from __future__ import annotations

# src/routes/anthropic/__init__.py
"""Anthropic 兼容路由包。"""

from src.routes.anthropic.messages import setup_routes  # noqa: F401

__all__ = ["setup_routes"]
