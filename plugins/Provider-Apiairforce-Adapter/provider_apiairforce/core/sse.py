


from __future__ import annotations

from typing import Any, Dict, Optional, Union

from provider_sdk.extensions.platform.sse_common import parse_openai_sse_line

__all__ = ["parse_sse_line"]


def parse_sse_line(data_str: str) -> Optional[Union[str, Dict[str, Any]]]:
    """解析 SSE data 行，返回文本增量或 usage。

    Args:
        data_str: SSE data 字段内容（不含 "data: " 前缀）。

    Returns:
        文本增量字符串、usage 字典，或 None（无法解析/终止块）。
    """
    return parse_openai_sse_line(data_str)
