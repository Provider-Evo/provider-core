


from __future__ import annotations

from typing import Any, Dict, Optional, Union

from provider_sdk.extensions.platform.sse_common import load_sse_json

__all__ = ["parse_sse_line"]


def parse_sse_line(data_str: str) -> Optional[Union[str, Dict[str, Any]]]:
    """解析 SSE data 字段内容（OpenAI 兼容 + tool_calls_delta）。

    Args:
        data_str: data: 前缀之后的字符串，已去除前缀和空白。

    Returns:
        str（文本片段）、dict（thinking/tool_calls_delta/usage）或 None（跳过）。
    """
    obj = load_sse_json(data_str)
    if obj is None:
        return None

    choices = obj.get("choices", [])
    if choices:
        delta = choices[0].get("delta", {})

        # tool_calls_delta 是 OpenRouter 特有字段，优先检查
        tc = delta.get("tool_calls")
        if tc:
            return {"tool_calls_delta": tc}

        reasoning_content = delta.get("reasoning_content")
        if reasoning_content:
            return {"thinking": reasoning_content}

        content = delta.get("content")
        if content:
            return content

    usage = obj.get("usage")
    if usage and isinstance(usage, dict):
        return {"usage": usage}

    return None

# =======================================================================
# 重导出 — 同包内协同模块的公共符号（保持外部 ``from .. import`` 路径稳定）
# =======================================================================

from .headers import (
    build_headers,
)

from .payload import (
    build_payload,
)

__all__ = [
    "build_headers",
    "build_payload",
]
