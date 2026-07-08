from __future__ import annotations

"""HTTP utility functions: fncall cleaning, buffer flushing, JSON parsing."""

from typing import Any, Tuple


def clean_fncall(content: str, platform_id: str = "", protocol_id: str = "") -> str:
    """Clean function-call tags (remove protocol-specific trigger tags).

    Args:
        content: Content string to clean.
        platform_id: Platform identifier (used to determine protocol).
        protocol_id: Protocol identifier (overrides platform_id).

    Returns:
        Cleaned content string.
    """
    from src.core.tools import get_protocol

    protocol = get_protocol(protocol_id=protocol_id, platform_id=platform_id)
    return protocol.clean_tags(content)


def safe_flush(
    buffer: str, platform_id: str = "", protocol_id: str = ""
) -> Tuple[str, str]:
    """Safely flush buffer — keep suffixes that might trigger tool calls.

    Scans the buffer tail for trigger-tag prefixes (not yet fully present),
    keeping the prefix in the buffer and flushing the complete part.

    Args:
        buffer: Current buffer content.
        platform_id: Platform identifier.
        protocol_id: Protocol identifier.

    Returns:
        (flushable_part, kept_part): Two strings whose concatenation equals the
        original buffer.
    """
    from src.core.tools import get_protocol

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

    Args:
        request: aiohttp.web.Request instance.

    Returns:
        Parsed JSON object, or None if parsing fails.
    """
    try:
        return await request.json()
    except Exception:
        return None
