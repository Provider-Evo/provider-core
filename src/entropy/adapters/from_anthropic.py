from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.entropy.core.types import TurnRequest
from src.routes.anthropic.convert import (
    _anth_messages_to_openai,
    _anth_tools_to_openai,
    _normalize_anth_content,
)
from src.routes.shared.thinking import (
    resolve_include_thinking_in_history,
    resolve_thinking_config,
)


def from_anthropic_messages_body(body: Dict[str, Any]) -> TurnRequest:
    """Anthropic messages 请求体 → TurnRequest。"""
    thinking_cfg = resolve_thinking_config(body, flavor="anthropic")
    include = resolve_include_thinking_in_history(body, thinking_cfg=thinking_cfg)
    system_str = _normalize_anth_content(body.get("system"))
    messages = _anth_messages_to_openai(
        body.get("messages", []),
        system_str,
        include_thinking_in_history=include,
    )
    tools = _anth_tools_to_openai(body.get("tools"))
    stop = body.get("stop_sequences")
    stop_list: Optional[List[str]] = None
    if stop is not None:
        stop_list = stop if isinstance(stop, list) else [str(stop)]
    return TurnRequest(
        model=body.get("model", ""),
        input=messages,
        tools=tools,
        thinking=thinking_cfg,
        stream=bool(body.get("stream", False)),
        max_output_tokens=body.get("max_tokens"),
        stop=stop_list,
        temperature=body.get("temperature"),
        top_p=body.get("top_p"),
        search=bool(body.get("search", False)),
    )
