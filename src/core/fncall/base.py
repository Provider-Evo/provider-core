# src/core/fncall/base.py
"""ToolProtocol 抽象基类 + 协议注册表。"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from src.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# 协议 ID 类型
# ---------------------------------------------------------------------------

VALID_PROTOCOL_IDS = ("xml", "original", "antml", "bracket", "custom", "nous")


# ---------------------------------------------------------------------------
# ToolProtocol 抽象基类
# ---------------------------------------------------------------------------


class ToolProtocol(ABC):
    """工具调用协议适配器抽象基类。

    每个协议实现以下方法：
    - render_prompt: 构建协议特定的 prompt（注入工具定义）
    - detect_start: 检测流式缓冲区中是否出现协议触发标记
    - parse: 从协议特定格式的文本中提取工具调用
    - parse_fragment: 直接解析已知的完整协议片段
    - clean_tags: 从响应文本中移除协议标签残留
    - get_trigger_tags: 返回触发标记列表（用于 safe_flush）
    - format_assistant_tool_calls: 将 tool_calls 渲染为协议格式（对话历史）
    - format_tool_result: 将工具结果渲染为协议格式
    - supports_streaming: 是否支持流式检测
    """

    @property
    @abstractmethod
    def id(self) -> str:
        """协议 ID，如 'xml', 'original', 'antml', 'bracket', 'custom'。"""
        ...

    def get_trigger_tags(self) -> List[str]:
        """返回触发标记字符串列表，用于 safe_flush 计算安全边界。"""
        return []

    @abstractmethod
    def render_prompt(
        self,
        tool_descs: str,
        lang: str,
        user_system_prompt: str = "",
        history_text: str = "",
        loop_warning: str = "",
        current_user_message: str = "",
    ) -> str:
        """构建完整的 prompt 字符串，注入工具定义。"""
        ...

    def detect_start(self, buffer: str) -> Tuple[bool, int]:
        """检测 buffer 中是否包含协议的触发标记。

        Returns:
            (found, position): found 为 True 时 position 是标记起始位置
        """
        return (False, -1)

    @abstractmethod
    def parse(
        self,
        text: str,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """从文本中提取工具调用，返回 (清理后文本, tool_calls 列表)。"""
        ...

    @abstractmethod
    def parse_fragment(
        self,
        fragment: str,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """将已知的完整协议片段直接解析为 tool_calls 列表。"""
        ...

    def clean_tags(self, content: str) -> str:
        """从响应文本中移除所有协议标签残留。"""
        return content.strip()

    def format_assistant_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
    ) -> str:
        """将 tool_call 对象列表渲染为协议特定的文本格式。"""
        return ""

    def format_tool_result(
        self,
        content: str,
        tool_name: str = "",
        is_error: bool = False,
    ) -> str:
        """将工具执行结果渲染为协议特定的文本格式。"""
        return ""

    def supports_streaming(self) -> bool:
        """该协议是否支持在流式响应中检测工具调用。"""
        return True


# ---------------------------------------------------------------------------
# 协议注册表
# ---------------------------------------------------------------------------

_PROTOCOL_REGISTRY: Dict[str, ToolProtocol] = {}


def register_protocol(protocol: ToolProtocol) -> None:
    """注册一个协议实现。"""
    _PROTOCOL_REGISTRY[protocol.id] = protocol
    logger.debug("已注册 fncall 协议: %s", protocol.id)


def get_protocol_by_id(protocol_id: str) -> ToolProtocol:
    """按 ID 获取已注册的协议。"""
    if protocol_id not in _PROTOCOL_REGISTRY:
        available = ", ".join(sorted(_PROTOCOL_REGISTRY.keys()))
        raise ValueError(
            "未知的 fncall 协议: {!r}（可用: {}）".format(protocol_id, available)
        )
    return _PROTOCOL_REGISTRY[protocol_id]


def list_protocols() -> List[str]:
    """返回所有已注册的协议 ID 列表。"""
    return sorted(_PROTOCOL_REGISTRY.keys())
