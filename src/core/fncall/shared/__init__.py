from __future__ import annotations

"""共享工具导出 → echotools 重导出。"""
from echotools.fncall.shared import *  # noqa: F401,F403
from echotools.fncall.shared import (
    LoopDetectionResult,
    _build_param_schema_index,
    _coerce_param_value,
    detect_tool_loop,
    format_tool_descs,
    normalize_content,
)
from echotools.ids.generator import uuid7 as _uuid7

from .norm import normalize_tool_call, normalize_tool_calls

__all__ = [
    "normalize_content",
    "format_tool_descs",
    "detect_tool_loop",
    "LoopDetectionResult",
    "_uuid7",
    "_coerce_param_value",
    "_build_param_schema_index",
    "normalize_tool_call",
    "normalize_tool_calls",
]
