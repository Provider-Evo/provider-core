from __future__ import annotations

# src/routes/openai/__init__.py
"""OpenAI 兼容路由包。"""

__all__ = ["setup_routes"]


def setup_routes(app):  # type: ignore[no-untyped-def]
    from src.routes.openai.routes import setup_routes as _impl

    return _impl(app)
