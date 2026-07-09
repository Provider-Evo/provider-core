from __future__ import annotations

from typing import Any, Dict, List


def build_payload(
    messages: List[Dict[str, Any]],
    model: str = "",
    stream: bool = True,
    **kw: Any,
) -> Dict[str, Any]:
    """Build chat completion request body.

    Args:
        messages: Message list.
        model: Model name.
        stream: Whether to stream the response.
        **kw: Extra parameters (temperature, top_p, max_tokens, stop, tools, tool_choice).

    Returns:
        Request body dictionary.
    """
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": stream,
    }
    if kw.get("temperature") is not None:
        payload["temperature"] = kw["temperature"]
    if kw.get("top_p") is not None:
        payload["top_p"] = kw["top_p"]
    if kw.get("max_tokens") is not None:
        payload["max_tokens"] = kw["max_tokens"]
    if kw.get("stop"):
        payload["stop"] = kw["stop"]
    if kw.get("tools"):
        payload["tools"] = kw["tools"]
    if kw.get("tool_choice"):
        payload["tool_choice"] = kw["tool_choice"]
    return payload
