# src/core/tools.py
"""向后兼容薄适配层。

所有实现已迁移到 src.core.fncall。
此模块重新导出相同的名称，使现有导入无需修改即可工作。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from src.core.fncall.shared.normalization import normalize_content, format_tool_descs
from src.core.fncall.shared.loop_detect import detect_tool_loop, LoopDetectionResult
from src.core.fncall.parsers.xml_parser import parse_fncall, parse_fncall_xml
from src.core.fncall.prompt.inject import inject_fncall
from src.core.fncall.base import ToolProtocol
from src.core.fncall.registry import get_protocol

# 内部函数导出（测试兼容）
from src.core.fncall.prompt.history import (
    _render_tool_call,
    _render_tool_result,
    _format_conversation_history,
    _normalize_messages,
)

__all__ = [
    "inject_fncall",
    "parse_fncall",
    "FncallStreamParser",
    "format_tool_descs",
    "normalize_content",
    "parse_fncall_xml",
    "detect_tool_loop",
    "LoopDetectionResult",
    # 内部函数（测试兼容）
    "_render_tool_call",
    "_render_tool_result",
    "_format_conversation_history",
    "_normalize_messages",
]


class FncallStreamParser:
    """向后兼容的流式解析器。

    旧签名: FncallStreamParser(tools=None)
    内部自动从配置获取当前协议并转发到协议感知的实现。
    """

    WAITING_FOR_TAG = "WAITING_FOR_TAG"
    IN_FUNCTION_CALLS = "IN_FUNCTION_CALLS"
    DONE = "DONE"

    def __init__(
        self,
        tools: Optional[List[Dict[str, Any]]] = None,
        protocol: Optional[Any] = None,
    ) -> None:
        if protocol is None:
            protocol = get_protocol()
        from src.core.fncall.parsers.stream import FncallStreamParser as _Real

        self._impl = _Real(protocol=protocol, tools=tools)

    def feed(self, chunk: str) -> None:
        self._impl.feed(chunk)

    def finalize(self) -> Tuple[str, List[Dict[str, Any]]]:
        return self._impl.finalize()

    @property
    def state(self) -> str:
        return self._impl.state

    @property
    def has_calls(self) -> bool:
        return self._impl.has_calls

    @property
    def partial_text(self) -> str:
        return self._impl.partial_text
