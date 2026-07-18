"""sse 模块 — Provider 适配器层。

职责：
    提供流式响应的 Server-Sent Events 解析与重组工具。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""



from __future__ import annotations

from typing import Any, Dict, Optional, Union

from provider_sdk.extensions.platform.sse_common import parse_openai_sse_line

__all__ = ["parse_sse_line"]


def parse_sse_line(data_str: str) -> Optional[Union[str, Dict[str, Any]]]:
    """解析单行 SSE data 字段内容（OpenAI 兼容格式）。

    Args:
        data_str: 去掉 ``data:`` 前缀后的原始字符串。

    Returns:
        文本增量（str）、usage 字典（dict）或 None（解析失败/无内容）。
    """
    return parse_openai_sse_line(data_str)
