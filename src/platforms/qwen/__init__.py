from __future__ import annotations

"""Qwen 平台适配器模块。

导出 QwenAdapter 类，供注册表自动发现和加载。
"""

from src.platforms.qwen.adapter import QwenAdapter

__all__ = ["QwenAdapter"]
