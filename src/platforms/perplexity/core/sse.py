from __future__ import annotations

import json
from typing import Any, Dict, Optional, Union


def parse_sse_line(data_str: str) -> Optional[Union[str, Dict[str, Any]]]:
    """Parse a single SSE data line from Perplexity's streaming response.

    Extracts text content, thinking summaries, or usage statistics from
    the JSON-encoded SSE event data.

    Args:
        data_str: The raw data string (after "data: " prefix stripped).

    Returns:
        A string (text delta), a dict (usage info), or None if unparseable.
    """
    try:
        obj = json.loads(data_str)
    except json.JSONDecodeError:
        return None

    if obj.get("choices") == [] and obj.get("usage"):
        return {"usage": obj["usage"]}

    if "blocks" in obj:
        for block in obj.get("blocks", []):
            diff = block.get("diff_block") or {}
            if diff.get("field") == "markdown_block":
                for patch in diff.get("patches", []):
                    value = patch.get("value")
                    if isinstance(value, dict):
                        value = value.get("answer") or ""
                    if isinstance(value, str) and value:
                        return value

    choices = obj.get("choices") or []
    if choices:
        delta = choices[0].get("delta") or {}
        content = delta.get("content")
        if content:
            return content

    return None
