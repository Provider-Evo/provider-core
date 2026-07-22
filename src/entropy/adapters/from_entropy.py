from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.entropy.core.types import TurnRequest
from src.routes.shared.thinking import (
    apply_thinking_history_policy,
    resolve_include_thinking_in_history,
    resolve_thinking_config,
)

_THINKING_BLOCK_TYPES = frozenset({"thinking", "reasoning", "redacted_thinking"})


def normalize_entropy_input_messages(
    messages: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """将 Entropy input 内容块展平为 gateway 可消费的 OpenAI 风格消息。"""
    out: List[Dict[str, Any]] = []
    for raw in messages:
        msg = dict(raw)
        content = msg.get("content")
        if not isinstance(content, list):
            out.append(msg)
            continue

        role = msg.get("role")
        thinking_parts: List[str] = []
        text_parts: List[str] = []
        tool_calls: List[Dict[str, Any]] = []

        for block in content:
            if not isinstance(block, dict):
                continue
            btype = str(block.get("type", "")).lower()
            if btype in _THINKING_BLOCK_TYPES:
                val = block.get("thinking") or block.get("text") or block.get("reasoning")
                if val:
                    thinking_parts.append(str(val))
            elif btype == "text":
                val = block.get("text")
                if val is not None:
                    text_parts.append(str(val))
            elif btype == "tool_call":
                tc = block.get("tool_call")
                if isinstance(tc, dict):
                    tool_calls.append(tc)
            elif btype == "input_text":
                val = block.get("text")
                if val is not None:
                    text_parts.append(str(val))

        if role == "assistant":
            if thinking_parts:
                joined = "\n".join(thinking_parts)
                msg["reasoning"] = joined
                msg["reasoning_content"] = joined
            msg["content"] = "\n".join(text_parts) if text_parts else (None if tool_calls else "")
            if tool_calls:
                msg["tool_calls"] = tool_calls
        else:
            msg["content"] = "\n".join(text_parts) if text_parts else ""
        out.append(msg)
    return out


def from_entropy_turn_body(body: Dict[str, Any]) -> TurnRequest:
    """Entropy 原生 /v1/turns 请求体（input 字段）→ TurnRequest。"""
    extra = body.get("extra_body") or body.get("extra") or {}
    thinking_cfg = resolve_thinking_config(body, extra=extra, flavor="entropy")
    include = resolve_include_thinking_in_history(
        body, extra=extra, thinking_cfg=thinking_cfg
    )
    raw_input = body.get("input", [])
    if not isinstance(raw_input, list):
        raw_input = []
    messages = apply_thinking_history_policy(raw_input, include)
    messages = normalize_entropy_input_messages(messages)

    stop = body.get("stop")
    stop_list: Optional[List[str]] = None
    if stop is not None:
        stop_list = stop if isinstance(stop, list) else [str(stop)]

    return TurnRequest(
        model=body.get("model", ""),
        input=messages,
        tools=body.get("tools"),
        thinking=thinking_cfg,
        stream=bool(body.get("stream", False)),
        max_output_tokens=body.get("max_output_tokens", body.get("max_tokens")),
        stop=stop_list,
        temperature=body.get("temperature"),
        top_p=body.get("top_p"),
        search=bool(extra.get("search")),
        metadata=body.get("metadata") or {},
        protocol_id=body.get("protocol", ""),
        platform=extra.get("platform", ""),
        tool_choice=body.get("tool_choice"),
    )


def from_entropy_compat_body(body: Dict[str, Any]) -> TurnRequest:
    """WebUI / 兼容层：messages 字段 → TurnRequest（OpenAI 形状，Entropy 思考配置）。"""
    from src.entropy.adapters.from_openai import from_openai_chat_body

    return from_openai_chat_body(body, flavor="entropy")
