from __future__ import annotations

"""思考链（reasoning / thinking）历史回传策略。"""

from typing import Any, Dict, List, Optional

_REASONING_KEYS = ("reasoning", "reasoning_content", "reasoning_details")
_HISTORY_FLAG_KEYS = (
    "include_thinking_in_history",
    "pass_thinking",
    "include_thinking",
)


def extract_reasoning_text(msg: Dict[str, Any]) -> str:
    """从 assistant 消息各字段提取思考文本。"""
    for key in ("reasoning", "reasoning_content"):
        val = msg.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    details = msg.get("reasoning_details")
    if isinstance(details, list):
        parts: List[str] = []
        for item in details:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if text:
                parts.append(str(text))
        if parts:
            return "".join(parts)
    return ""


def resolve_include_thinking_in_history(
    body: Dict[str, Any],
    *,
    extra: Optional[Dict[str, Any]] = None,
    thinking_enabled: Optional[bool] = None,
) -> bool:
    """解析是否将历史消息中的思考链传给下游。

    显式参数优先；未指定时默认与本次请求的 thinking 开关一致。
    """
    extra = extra if extra is not None else (body.get("extra_body") or body.get("extra") or {})

    for key in _HISTORY_FLAG_KEYS:
        if key in body:
            return bool(body[key])
        if key in extra:
            return bool(extra[key])

    if thinking_enabled is not None:
        return thinking_enabled
    return False


def apply_thinking_history_policy(
    messages: List[Dict[str, Any]],
    include: bool,
) -> List[Dict[str, Any]]:
    """按策略保留或剥离消息中的思考链字段。"""
    if include:
        return _normalize_messages_with_reasoning(messages)
    return _strip_reasoning_from_messages(messages)


def _strip_reasoning_from_messages(
    messages: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for m in messages:
        msg = dict(m)
        for key in _REASONING_KEYS:
            msg.pop(key, None)
        out.append(msg)
    return out


def _normalize_messages_with_reasoning(
    messages: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for m in messages:
        msg = dict(m)
        if msg.get("role") == "assistant":
            text = extract_reasoning_text(msg)
            if text:
                msg["reasoning"] = text
                msg.setdefault("reasoning_content", text)
        else:
            for key in _REASONING_KEYS:
                msg.pop(key, None)
        out.append(msg)
    return out
