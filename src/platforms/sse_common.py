"""Shared SSE parser for OpenAI-compatible streaming APIs.

Most platforms follow the same SSE format:
- data: {"choices":[{"delta":{"content":"...","reasoning_content":"..."}}]}
- data: {"usage":{...}}
- data: [DONE]

This module provides two levels of API:

- :func:`load_sse_json` -- low-level: parse JSON, handle [DONE]/error/empty.
- :func:`parse_openai_sse_line` -- high-level: extract text/thinking/usage.

Platforms with custom extensions (tool_calls, etc.) should use
:func:`load_sse_json` and add their own field extraction.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, Union


def load_sse_json(data_str: str) -> Optional[Dict[str, Any]]:
    """Low-level SSE JSON parser.

    Handles [DONE], empty strings, JSON decode errors, and error fields.

    Args:
        data_str: Content after ``data:`` prefix, stripped of whitespace.

    Returns:
        Parsed JSON dict, or None if the event should be skipped.

    Raises:
        ValueError: When the SSE event contains an ``error`` field.
    """
    if not data_str or data_str == "[DONE]":
        return None

    try:
        obj = json.loads(data_str)
    except (json.JSONDecodeError, ValueError):
        return None

    if "error" in obj:
        raise ValueError("SSE error: {}".format(obj["error"]))

    return obj


def parse_openai_sse_line(data_str: str) -> Optional[Union[str, Dict[str, Any]]]:
    """Parse an OpenAI-compatible SSE data field.

    Handles the standard format: choices/delta/content/reasoning_content/usage.

    Args:
        data_str: Content after ``data:`` prefix, stripped of whitespace.

    Returns:
        str (text chunk), dict (thinking/usage metadata), or None (skip event).

    Raises:
        ValueError: When the SSE event contains an ``error`` field.
    """
    obj = load_sse_json(data_str)
    if obj is None:
        return None

    choices = obj.get("choices", [])
    if not choices:
        usage = obj.get("usage")
        if usage:
            return {"usage": usage}
        return None

    choice = choices[0]
    delta = choice.get("delta", {})

    reasoning_content = delta.get("reasoning_content")
    if reasoning_content:
        return {"thinking": reasoning_content}

    content = delta.get("content")
    if content:
        return content

    usage = obj.get("usage")
    if usage:
        return {"usage": usage}

    return None
