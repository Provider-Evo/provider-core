from __future__ import annotations

# src/platforms/azuretranslate/adapter.py
"""Azure Translator 平台适配器入口——仅负责导出适配器类。"""

from src.platforms.azuretranslate.util import Adapter, AzureTranslateAdapter

__all__ = ["AzureTranslateAdapter", "Adapter"]
