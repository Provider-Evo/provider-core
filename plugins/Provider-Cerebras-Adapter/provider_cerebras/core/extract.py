


from __future__ import annotations

from typing import Any, Dict, Optional


def extract_usage(usage_obj: Any) -> Dict[str, int]:
    """从 SDK 响应的 usage 对象提取 token 用量。

    Args:
        usage_obj: Cerebras SDK 返回的 usage 对象（含 prompt_tokens 等属性）。

    Returns:
        标准 usage 字典，包含 prompt_tokens、completion_tokens、total_tokens。
    """
    return {
        "prompt_tokens": int(getattr(usage_obj, "prompt_tokens", 0)),
        "completion_tokens": int(getattr(usage_obj, "completion_tokens", 0)),
        "total_tokens": int(getattr(usage_obj, "total_tokens", 0)),
    }


def extract_delta_content(chunk: Any) -> Optional[str]:
    """从流式 chunk 中提取增量文本内容。

    Args:
        chunk: Cerebras SDK 流式响应的单个 chunk 对象。

    Returns:
        增量文本字符串，若无内容则返回 None。
    """
    if not chunk.choices:
        return None
    delta = chunk.choices[0].delta
    if delta is None:
        return None
    content = getattr(delta, "content", None)
    if not content:
        return None
    return content


def extract_nonstream_content(resp: Any) -> Optional[str]:
    """从非流式响应中提取完整文本内容。

    Args:
        resp: Cerebras SDK 非流式响应对象。

    Returns:
        完整文本字符串，若无内容则返回 None。
    """
    if not resp.choices:
        return None
    message = resp.choices[0].message
    if message is None:
        return None
    content = getattr(message, "content", None)
    if not content:
        return None
    return content
