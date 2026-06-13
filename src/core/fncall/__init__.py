"""fncall 协议包 → echotools 重导出。"""
from echotools.fncall import *  # noqa: F401,F403
from echotools.fncall import (
    inject_fncall,
    parse_fncall,
    parse_fncall_xml,
    FncallStreamParser,
    format_tool_descs,
    normalize_content,
    detect_tool_loop,
    LoopDetectionResult,
    ToolProtocol,
    get_protocol,
    get_protocol_by_id,
    register_protocol,
    list_protocols,
)
