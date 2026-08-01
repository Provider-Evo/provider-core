from __future__ import annotations

"""fncall 协议包。"""
from echotools.exec.fncall.parsers.stream import FncallStreamParser
from echotools.exec.fncall.shared.loop_detect import LoopDetectionResult, detect_tool_loop
from echotools.exec.fncall.shared.normalization import (
    format_tool_descs,
    normalize_content,
)
from echotools.exec.protocol.base import (
    ToolProtocol,
    get_protocol_by_id,
    register_protocol,
)

from src.core.fncall.parsers import parse_fncall, parse_fncall_xml
from src.core.fncall.prompt.inject import inject_fncall
from src.core.fncall.reg import get_protocol, list_protocols

__all__ = [
    "FncallStreamParser",
    "LoopDetectionResult",
    "ToolProtocol",
    "detect_tool_loop",
    "format_tool_descs",
    "get_protocol",
    "get_protocol_by_id",
    "inject_fncall",
    "list_protocols",
    "normalize_content",
    "parse_fncall",
    "parse_fncall_xml",
    "register_protocol",
]
