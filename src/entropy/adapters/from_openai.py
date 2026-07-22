from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.entropy.core.types import TurnRequest
from src.routes.openai.chat.helpers import _extract_upload_files, _normalize_messages
from src.routes.shared.thinking import ThinkingConfig, resolve_thinking_config


def from_openai_chat_body(
    body: Dict[str, Any],
    *,
    flavor: str = "openai",
) -> TurnRequest:
    """OpenAI chat/completions 请求体 → TurnRequest。"""
    extra = body.get("extra_body") or body.get("extra") or {}
    messages = body.get("messages", [])
    thinking_cfg = resolve_thinking_config(body, extra=extra, flavor=flavor)  # type: ignore[arg-type]
    from src.routes.shared.thinking import resolve_include_thinking_in_history

    include = resolve_include_thinking_in_history(
        body, extra=extra, thinking_cfg=thinking_cfg
    )
    normalized = _normalize_messages(messages, include_thinking_in_history=include)
    stop = body.get("stop")
    stop_list: Optional[List[str]] = None
    if stop is not None:
        stop_list = stop if isinstance(stop, list) else [str(stop)]
    return TurnRequest(
        model=body.get("model", ""),
        input=normalized,
        tools=body.get("tools"),
        thinking=thinking_cfg,
        stream=bool(body.get("stream", False)),
        max_output_tokens=body.get("max_tokens"),
        stop=stop_list,
        temperature=body.get("temperature"),
        top_p=body.get("top_p"),
        search=bool(extra.get("search")),
        protocol_id=body.get("protocol", ""),
        platform=extra.get("platform", ""),
        tool_choice=body.get("tool_choice"),
        upload_files=_extract_upload_files(normalized) or None,
    )
