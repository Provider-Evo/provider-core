from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from src.foundation.config.resolve import resolve_model

from src.routes.anthropic.convert.format_convert import _is_thinking, _tc_id


def _openai_tc_to_anth(
    tc: Dict[str, Any],
) -> Dict[str, Any]:
    """将 OpenAI tool_call 转换为 Anthropic tool_use content block。

    id 必须以 toolu_ 开头；若上游 id 不符合，生成新的合规 id。
    """
    func = tc.get("function", {})
    args_raw = func.get("arguments", "{}")
    if isinstance(args_raw, dict):
        inp = args_raw
    else:
        try:
            inp = json.loads(args_raw)
        except (json.JSONDecodeError, ValueError):
            inp = {}

    raw_id: str = tc.get("id") or ""
    tool_id = raw_id if raw_id.startswith("toolu_") else _tc_id()

    return {
        "type": "tool_use",
        "id": tool_id,
        "name": func.get("name", ""),
        "input": inp,
    }


def _build_dispatch_kwargs(
    body: Dict[str, Any],
    messages: List[Dict[str, Any]],
    stream: bool,
    registry: Any,
    tools: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """构建 gateway.dispatch 调用参数。"""
    stop = body.get("stop_sequences")
    if stop is not None and isinstance(stop, list):
        stop_val: Optional[List[str]] = stop
    elif stop is not None:
        stop_val = [str(stop)]
    else:
        stop_val = None

    return {
        "registry": registry,
        "messages": messages,
        "model": resolve_model(body.get("model", ""), "anthropic"),
        "stream": stream,
        "tools": tools,
        "thinking": _is_thinking(body),
        "search": bool(body.get("search", False)),
        "temperature": body.get("temperature"),
        "top_p": body.get("top_p"),
        "max_tokens": body.get("max_tokens", 4096),
        "stop": stop_val,
    }
