"""tools 模块 — 项目标准模块。

职责：
    作为 Provider-Evo 项目标准模块，提供 tools 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""

from echotools.fncall import (
    FncallStreamParser,
    LoopDetectionResult,
    detect_tool_loop,
    format_tool_descs,
    inject_fncall,
    normalize_content,
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
    # 循环检测
    "detect_tool_loop",
    "LoopDetectionResult",
    # 协议抽象
    "ToolProtocol",
    "get_protocol",
]
