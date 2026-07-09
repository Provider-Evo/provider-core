from __future__ import annotations

"""共享工具导出 → echotools 重导出。"""
from echotools.fncall.shared import *  # noqa: F401,F403
from echotools.fncall.shared import (
    normalize_content,
    format_tool_descs,
    detect_tool_loop,
    LoopDetectionResult,
    _coerce_param_value,
    _build_param_schema_index,
)
from echotools.ids.generator import uuid7 as _uuid7

__all__ = [
    "normalize_content",
    "format_tool_descs",
    "detect_tool_loop",
    "LoopDetectionResult",
    "_uuid7",
    "_coerce_param_value",
    "_build_param_schema_index",
]
