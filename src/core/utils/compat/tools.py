
from echotools import (
    FncallStreamParser,
    LoopDetectionResult,
    detect_tool_loop,
    inject_fncall,
)
from echotools.exec.fncall.shared.normalization import (
    format_tool_descs,
    normalize_content,
    normalize_tool_call,
    normalize_tool_calls,
)
from echotools.exec.protocol.base import ToolProtocol

from src.core.fncall.parsers import parse_fncall, parse_fncall_xml
from src.core.fncall.reg import get_protocol

__all__ = [
    "inject_fncall",
    "parse_fncall",
    "parse_fncall_xml",
    "FncallStreamParser",
    "format_tool_descs",
    "normalize_content",
    "normalize_tool_call",
    "normalize_tool_calls",
    "detect_tool_loop",
    "LoopDetectionResult",
    "ToolProtocol",
    "get_protocol",
]
