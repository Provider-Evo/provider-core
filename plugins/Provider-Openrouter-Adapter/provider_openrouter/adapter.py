from __future__ import annotations

# src/platforms/openrouter/adapter.py
"""OpenRouter 平台适配器入口——仅负责导出适配器类。"""

from src.platforms.openrouter.util import Adapter, OpenRouterAdapter

__all__ = ["OpenRouterAdapter", "Adapter"]
