
from echotools.fncall import (
    FncallStreamParser,
    LoopDetectionResult,
    detect_tool_loop,
    format_tool_descs,
    inject_fncall,
    normalize_content,
    normalize_tool_call,
    normalize_tool_calls,
    parse_fncall,
    parse_fncall_xml,
)
from echotools.fncall.registry import get_protocol
from echotools.protocol.base import ToolProtocol

__all__ = [
    # 注入与解析
    "inject_fncall",
    "parse_fncall",
    "parse_fncall_xml",
    "FncallStreamParser",
    # 格式化与标准化
    "format_tool_descs",
    "normalize_content",
    "normalize_tool_call",
    "normalize_tool_calls",
    # 循环检测
    "detect_tool_loop",
    "LoopDetectionResult",
    # 协议抽象
    "ToolProtocol",
    "get_protocol",
]
