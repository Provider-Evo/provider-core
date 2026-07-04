from __future__ import annotations

# src/routes/openai/__init__.py
"""OpenAI 兼容路由包。"""

from src.routes.openai.routes import setup_routes  # noqa: F401

__all__ = ["setup_routes"]
