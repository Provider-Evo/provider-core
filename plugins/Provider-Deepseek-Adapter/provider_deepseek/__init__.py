from __future__ import annotations

"""DeepSeek 平台适配器模块。

导出 DeepseekAdapter 类与 Adapter 通用别名，供注册表自动发现和加载。
"""

from provider_deepseek.adapter import Adapter, DeepseekAdapter

__all__ = ["Adapter", "DeepseekAdapter"]
