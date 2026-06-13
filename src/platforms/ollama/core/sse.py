from __future__ import annotations

"""Ollama 流式响应解析。

Ollama 使用逐行 JSON 而非 SSE 格式。
"""

import json
from typing import Any, Dict, Optional, Union


def parse_ollama_line(
    line: bytes,
) -> Optional[Union[str, Dict[str, Any]]]:
    """解析 Ollama 流式响应的单行 JSON。

    Ollama 的流式响应不是 SSE 格式，而是逐行 JSON。

    Args:
        line: 原始字节行（已去除首尾空白）。

    Returns:
        str（文本片段）、dict（usage）或 None（跳过）。

    Raises:
        ValueError: 响应中包含 error 字段时抛出。
    """
    if not line:
        return None

    try:
        data = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None

    if "error" in data:
        raise ValueError("ollama error: {}".format(data["error"]))

    content = data.get("message", {}).get("content", "")

    if data.get("done"):
        usage = _extract_usage(data)
        if usage:
            return {"usage": usage}
        return None

    if content:
        return content

    return None


def _extract_usage(data: Dict[str, Any]) -> Dict[str, int]:
    """从 Ollama 响应中提取 usage 信息。

    Args:
        data: JSON 响应数据。

    Returns:
        包含 prompt_tokens 和/或 completion_tokens 的字典。
    """
    usage: Dict[str, int] = {}
    if "prompt_eval_count" in data:
        usage["prompt_tokens"] = data["prompt_eval_count"]
    if "eval_count" in data:
        usage["completion_tokens"] = data["eval_count"]
    return usage
