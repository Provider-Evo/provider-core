# src/core/fncall/__init__.py
"""fncall 协议包。

向后兼容：重新导出与 src.core.tools 相同的名称，
使现有导入无需修改即可工作。
"""

from __future__ import annotations

# 向后兼容导出（与 src.core.tools 相同）
from src.core.fncall.shared.normalization import normalize_content, format_tool_descs
from src.core.fncall.shared.loop_detect import detect_tool_loop, LoopDetectionResult
from src.core.fncall.parsers.xml_parser import parse_fncall, parse_fncall_xml
from src.core.fncall.parsers.stream import FncallStreamParser
from src.core.fncall.prompt.inject import inject_fncall

# 协议基础设施
from src.core.fncall.base import (
    ToolProtocol,
    register_protocol,
    get_protocol_by_id,
    VALID_PROTOCOL_IDS,
)
from src.core.fncall.registry import get_protocol, list_protocols

__all__ = [
    # 向后兼容
    "inject_fncall",
    "parse_fncall",
    "FncallStreamParser",
    "format_tool_descs",
    "normalize_content",
    "parse_fncall_xml",
    "detect_tool_loop",
    "LoopDetectionResult",
    # 协议基础设施
    "ToolProtocol",
    "get_protocol",
    "get_protocol_by_id",
    "register_protocol",
    "list_protocols",
    "VALID_PROTOCOL_IDS",
]
