from __future__ import annotations

# src/routes/main/__init__.py
"""主路由包——健康检查、模型列表、状态、能力矩阵、函数调用。"""

from src.routes.main.routes import setup_routes  # noqa: F401

__all__ = ["setup_routes"]
