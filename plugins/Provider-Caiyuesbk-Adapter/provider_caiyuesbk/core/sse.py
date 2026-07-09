"""Caiyuesbk SSE 解析（无状态层）。"""

from __future__ import annotations

from typing import Any, Dict, Optional, Union

from src.platforms.sse_common import parse_openai_sse_line

__all__ = ["parse_sse_line"]


def parse_sse_line(data_str: str) -> Optional[Union[str, Dict[str, Any]]]:
    """解析单行 SSE data 字段内容（OpenAI 兼容格式）。

    Args:
        data_str: 去掉 ``data:`` 前缀后的原始字符串。

    Returns:
        文本增量（str）、usage 字典（dict）或 None（解析失败/无内容）。
    """
    return parse_openai_sse_line(data_str)
