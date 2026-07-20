

# src/platforms/deepseek/adapter.py
"""DeepSeek 平台适配器入口——仅负责导出适配器类。"""

from provider_deepseek.util import Adapter, DeepseekAdapter

__all__ = ["Adapter", "DeepseekAdapter"]

# =======================================================================
# 重导出 — 同包内协同模块的公共符号（保持外部 ``from .. import`` 路径稳定）
# =======================================================================

from .util import (
    build_payload,
    parse_sse_line,
)

__all__ = [
    "build_payload",
    "parse_sse_line",
]
