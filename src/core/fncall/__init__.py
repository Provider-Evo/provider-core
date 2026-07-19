from __future__ import annotations

"""fncall 协议包 → echotools 重导出。"""
from echotools.fncall import *  # noqa: F401,F403
from echotools.fncall import (
    FncallStreamParser,
    LoopDetectionResult,
    ToolProtocol,
    detect_tool_loop,
    format_tool_descs,
    get_protocol,
    get_protocol_by_id,
    inject_fncall,
    list_protocols,
    normalize_content,
    parse_fncall,
    parse_fncall_xml,
    register_protocol,
)
