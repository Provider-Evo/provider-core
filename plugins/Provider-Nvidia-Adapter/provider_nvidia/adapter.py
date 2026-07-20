

# src/platforms/nvidia/adapter.py
"""Nvidia 平台适配器入口——仅负责导出适配器类。"""

from provider_nvidia.util import Adapter, NvidiaAdapter

__all__ = ["NvidiaAdapter", "Adapter"]
