from __future__ import annotations

"""Shared HTTP utilities for route handlers."""

import re
from typing import Any, Tuple

import aiohttp.web

# Pre-compiled regex for cleaning fncall tags from response text
_FNCALL_CLEAN_NEW_RE = re.compile(
    r"<function_calls>\s*<invoke[^>]*>.*?</invoke>\s*</function_calls>",
    re.DOTALL,
)
_FNCALL_CLEAN_OLD_RE = re.compile(
    r"<function=[^>]*>.*?</function>",
    re.DOTALL,
)

# fncall detection tag (for _safe_flush)
_FNCALL_OPEN_TAG = "<function_calls>"
_FNCALL_TAG_LEN = len(_FNCALL_OPEN_TAG)


def clean_fncall(content: str) -> str:
    """Remove all fncall tag remnants from response text.

    Supports both new format (<function_calls>...</function_calls>)
    and old format (<function=name>...</function>).

    Args:
        content: Raw text.

    Returns:
        Cleaned text (stripped).
    """
    content = _FNCALL_CLEAN_NEW_RE.sub("", content)
    content = _FNCALL_CLEAN_OLD_RE.sub("", content)
    return content.strip()


def safe_flush(buffer: str) -> Tuple[str, str]:
    """Extract safe-to-output prefix from buffer, preserving potential fncall tag suffix.

    Args:
        buffer: Current text buffer.

    Returns:
        (safe, remain): safe is the outputtable prefix, remain is the pending suffix.
    """
    buf_len = len(buffer)
    safe_end = buf_len
    check_len = min(_FNCALL_TAG_LEN, buf_len)
    for length in range(check_len, 0, -1):
        start = buf_len - length
        if _FNCALL_OPEN_TAG.startswith(buffer[start:]):
            safe_end = start
            break
    return buffer[:safe_end], buffer[safe_end:]


async def get_json(request: aiohttp.web.Request) -> Any:
    """Safely parse request JSON body.

    Args:
        request: aiohttp request object.

    Returns:
        Parsed dict, or None on failure.
    """
    try:
        return await request.json()
    except Exception:
        return None
