"""http_utils 模块 — 项目标准模块。

职责：
    作为 Provider-Evo 项目标准模块，提供 http_utils 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""

from typing import Any, Tuple


def clean_fncall(content: str, platform_id: str = "", protocol_id: str = "") -> str:
    """中文说明：clean_fncall。

    Clean function-call tags (remove protocol-specific trigger tags).

    Args:
        content: Content string to clean.
        platform_id: Platform identifier (used to determine protocol).
        protocol_id: Protocol identifier (overrides platform_id).

    Returns:
        Cleaned content string."""
    from src.core.utils.compat.tools import get_protocol

    protocol = get_protocol(protocol_id=protocol_id, platform_id=platform_id)
    return protocol.clean_tags(content)


def safe_flush(
    buffer: str,
    platform_id: str = "",
    protocol_id: str = "",
    protocol: Any = None,
) -> Tuple[str, str]:
    """中文说明：safe_flush。

    Safely flush buffer — keep suffixes that might trigger tool calls.

    Scans the buffer tail for trigger-tag prefixes (not yet fully present),
    keeping the prefix in the buffer and flushing the complete part.

    Args:
        buffer: Current buffer content.
        platform_id: Platform identifier.
        protocol_id: Protocol identifier.

    Returns:
        (flushable_part, kept_part): Two strings whose concatenation equals the
        original buffer."""
    if protocol is None:
        from src.core.utils.compat.tools import get_protocol

        protocol = get_protocol(protocol_id=protocol_id, platform_id=platform_id)
    tags = protocol.get_trigger_tags()
    if not tags:
        return buffer, ""

    buf_len = len(buffer)
    max_keep = max(len(t) - 1 for t in tags)
    check_len = min(max_keep, buf_len)

    for length in range(check_len, 0, -1):
        suffix = buffer[buf_len - length :]
        if any(tag.startswith(suffix) and suffix != tag for tag in tags):
            return buffer[: buf_len - length], buffer[buf_len - length :]

    if buf_len <= max_keep:
        if any(tag.startswith(buffer) and buffer != tag for tag in tags):
            return "", buffer

    return buffer, ""


async def get_json(request: Any) -> Any:
    """Safely read request JSON body, returning None on failure.

    Reuses body parsed by stats middleware when present to avoid double
    ``json.loads`` on large POST payloads.
    """
    cached = request.get("_parsed_json_body")
    if cached is not None:
        return cached
    try:
        body = await request.json()
        request["_parsed_json_body"] = body
        return body
    except Exception:
        return None
