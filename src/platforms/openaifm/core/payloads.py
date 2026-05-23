from __future__ import annotations

from typing import Any, Dict, List, Optional

from .tts import DEFAULT_MODEL


def build_payload(
    messages: List[Dict[str, Any]],
    model: str = "",
    stream: bool = True,
    tools: Optional[List[Dict[str, Any]]] = None,
    **kw: Any,
) -> Dict[str, Any]:
    """Build chat request payload (placeholder; openaifm is mainly TTS).

    Args:
        messages: Message list.
        model: Model name.
        stream: Whether streaming.
        tools: Optional tool definitions.
        **kw: Extra parameters.

    Returns:
        Payload dictionary.
    """
    payload: Dict[str, Any] = {
        "model": model or DEFAULT_MODEL,
        "messages": messages,
        "stream": stream,
    }
    if tools:
        payload["tools"] = tools
    payload.update(kw)
    return payload
