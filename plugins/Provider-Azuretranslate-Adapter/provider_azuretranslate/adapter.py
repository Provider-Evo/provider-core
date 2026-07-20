

# src/platforms/azuretranslate/adapter.py
"""Azure Translator 平台适配器入口——仅负责导出适配器类。"""

from provider_azuretranslate.util import Adapter, AzureTranslateAdapter

__all__ = ["AzureTranslateAdapter", "Adapter"]
