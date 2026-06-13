"""工具调用统一接口 → echotools 重导出。"""
from __future__ import annotations

from echotools.fncall import (
    inject_fncall,
    parse_fncall,
    parse_fncall_xml,
    FncallStreamParser,
    format_tool_descs,
    normalize_content,
    detect_tool_loop,
    LoopDetectionResult,
)
from echotools.protocol.base import ToolProtocol
from echotools.fncall.registry import get_protocol

__all__ = [
    "inject_fncall",
    "parse_fncall",
    "parse_fncall_xml",
    "FncallStreamParser",
    "format_tool_descs",
    "normalize_content",
    "detect_tool_loop",
    "LoopDetectionResult",
    "ToolProtocol",
    "get_protocol",
]
