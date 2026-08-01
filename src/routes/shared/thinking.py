from __future__ import annotations

"""思考链（reasoning / thinking）历史回传与请求解析。"""

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional

ThinkingMode = Literal["off", "on", "auto"]
ThinkingLevel = Literal["none", "low", "medium", "high", "xhigh", "max", "auto"]

_LEVEL_ALIASES = {
    "minimal": "low",
    "default": "medium",
}

_CANONICAL_LEVELS = frozenset({"none", "low", "medium", "high", "xhigh", "max", "auto"})
_INJECTION_MODES = frozenset({"off", "on", "auto"})

_LEVEL_NORMALIZE = {
    "none": "none",
    "off": "none",
    "disabled": "none",
    "disable": "none",
    "false": "none",
    "no": "none",
    "never": "none",
    "low": "low",
    "medium": "medium",
    "med": "medium",
    "high": "high",
    "xhigh": "xhigh",
    "extra_high": "xhigh",
    "extrahigh": "xhigh",
    "max": "max",
    "maximum": "max",
    "auto": "auto",
    "automatic": "auto",
    "adaptive": "auto",
    "interleaved": "auto",
}

_MODE_NORMALIZE = {
    "off": "off",
    "disabled": "off",
    "disable": "off",
    "false": "off",
    "none": "off",
    "no": "off",
    "never": "off",
    "on": "on",
    "enabled": "on",
    "enable": "on",
    "true": "on",
    "force": "on",
    "forced": "on",
    "required": "on",
    "must": "on",
    "static": "on",
    "thinking": "on",
    "auto": "auto",
    "automatic": "auto",
    "adaptive": "auto",
    "interleaved": "auto",
}

_REASONING_KEYS = ("reasoning", "reasoning_content", "reasoning_details")
_THINKING_BLOCK_TYPES = frozenset({"thinking", "reasoning", "redacted_thinking"})


@dataclass(frozen=True)
class ThinkingConfig:
    """Entropy 规范思考配置。

    level: echotools 思考挡位（none/low/medium/high/xhigh/max/auto）。
    mode: 下游 dispatch 用 off/on/auto（可由 level 推导）。
    interleaved_history: 交错历史开关（非 mode）。
    """

    level: Optional[ThinkingLevel] = None
    mode: Optional[ThinkingMode] = None
    max_tokens: Optional[int] = None
    interleaved_history: bool = False

    @property
    def enabled(self) -> bool:
        if self.level is not None:
            return self.level != "none"
        return self.mode in ("on", "auto")

    @property
    def effective_level(self) -> Optional[ThinkingLevel]:
        if self.level is not None:
            return self.level
        return mode_to_thinking_level(self.mode)

    @property
    def effective_mode(self) -> Optional[ThinkingMode]:
        if self.mode is not None:
            return self.mode
        return level_to_thinking_mode(self.level)


_HISTORY_FLAG_KEYS = (
    "include_thinking_in_history",
    "pass_thinking",
    "include_thinking",
    "interleaved_history",
)


def normalize_thinking_level(level: Any) -> Optional[str]:
    if level is None:
        return None
    key = str(level).strip().lower()
    if not key:
        return None
    if key in _CANONICAL_LEVELS:
        return key
    if key in _LEVEL_ALIASES:
        return _LEVEL_ALIASES[key]
    return _LEVEL_NORMALIZE.get(key)


def normalize_thinking_mode(mode: Any) -> Optional[str]:
    if mode is None:
        return None
    key = str(mode).strip().lower()
    if not key:
        return None
    if key in _INJECTION_MODES:
        return key
    return _MODE_NORMALIZE.get(key)


def extract_reasoning_text(msg: Dict[str, Any]) -> str:
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

    content = msg.get("content")
    if isinstance(content, list):
        parts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = str(block.get("type", "")).strip().lower()
            if btype in ("thinking", "redacted_thinking"):
                val = block.get("thinking") or block.get("data")
            elif btype == "reasoning":
                val = block.get("text") or block.get("reasoning")
            else:
                val = None
            if val:
                parts.append(str(val).strip())
        if parts:
            return "\n".join(parts)
    return ""


def parse_interleaved_history(
    body: Dict[str, Any],
    extra: Optional[Dict[str, Any]] = None,
    thinking: Any = None,
) -> bool:
    extra = extra or {}
    if thinking is None:
        thinking = body.get("thinking")
    for key in ("interleaved_history", "include_in_history"):
        if key in body:
            return bool(body[key])
        if key in extra:
            return bool(extra[key])
    if isinstance(thinking, dict):
        for key in ("interleaved_history", "include_in_history"):
            if key in thinking:
                return bool(thinking[key])
    return False


def _strip_thinking_blocks(content: List[Any]) -> List[Any]:
    kept: List[Any] = []
    for block in content:
        if isinstance(block, dict) and str(block.get("type", "")).lower() in _THINKING_BLOCK_TYPES:
            continue
        kept.append(block)
    return kept


def _collapse_text_content(blocks: List[Any]) -> Any:
    if len(blocks) == 1:
        only = blocks[0]
        if isinstance(only, dict) and only.get("type") == "text":
            return only.get("text", "")
    return blocks


def _strip_reasoning_from_message(msg: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(msg)
    for key in _REASONING_KEYS:
        out.pop(key, None)
    content = out.get("content")
    if isinstance(content, list):
        stripped = _strip_thinking_blocks(content)
        out["content"] = _collapse_text_content(stripped) if stripped else ""
    return out


def _normalize_message_with_reasoning(msg: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(msg)
    if out.get("role") != "assistant":
        for key in _REASONING_KEYS:
            out.pop(key, None)
        return out

    text = extract_reasoning_text(out)
    if text:
        out["reasoning"] = text
        out.setdefault("reasoning_content", text)
    return out


def apply_thinking_history_policy(
    messages: List[Dict[str, Any]],
    include: bool,
) -> List[Dict[str, Any]]:
    if include:
        return [_normalize_message_with_reasoning(dict(m)) for m in messages]
    return [_strip_reasoning_from_message(dict(m)) for m in messages]


def _parse_interleaved_history(
    body: Dict[str, Any],
    extra: Dict[str, Any],
    thinking: Any,
) -> bool:
    return parse_interleaved_history(body, extra, thinking)


def level_to_thinking_mode(level: Optional[str]) -> Optional[ThinkingMode]:
    normalized = normalize_thinking_level(level)
    if normalized is None:
        return None
    if normalized == "none":
        return "off"
    if normalized == "auto":
        return "auto"
    return "on"


def mode_to_thinking_level(mode: Optional[str]) -> Optional[ThinkingLevel]:
    normalized = normalize_thinking_mode(mode)
    if normalized is None:
        return None
    if normalized == "off":
        return "none"
    if normalized == "on":
        return "medium"
    if normalized == "auto":
        return "auto"
    return None


def _map_to_thinking_level(raw: Any) -> Optional[ThinkingLevel]:
    """映射 thinking / effort / reasoning 值为 echotools thinking_level。"""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return "medium" if raw else "none"
    if isinstance(raw, (int, float)):
        return "none" if raw == 0 else "medium"
    key = str(raw).strip().lower()
    if not key:
        return None
    level = normalize_thinking_level(key)
    if level is not None:
        return level  # type: ignore[return-value]
    if key in _LEVEL_ALIASES:
        return _LEVEL_ALIASES[key]  # type: ignore[return-value]
    mode = normalize_thinking_mode(key)
    if mode is not None:
        return mode_to_thinking_level(mode)
    return None


def _entropy_thinking_config(
    body: Dict[str, Any],
    extra: Dict[str, Any],
) -> ThinkingConfig:
    thinking = body.get("thinking")
    level: Optional[ThinkingLevel] = _as_thinking_level(
        extra.get("thinking_level", body.get("thinking_level"))
    )
    max_tokens: Optional[int] = None
    interleaved_history = _parse_interleaved_history(body, extra, thinking)
    if isinstance(thinking, dict):
        if level is None:
            level = _map_to_thinking_level(thinking.get("level"))
        if level is None:
            level = _map_to_thinking_level(thinking.get("mode"))
        max_tokens = _as_int(thinking.get("max_tokens"))
    elif thinking is not None and level is None:
        level = _map_to_thinking_level(thinking)
    else:
        if level is None:
            level = _map_to_thinking_level(extra.get("thinking_mode", body.get("thinking_mode")))
        if level is None and "thinking" in extra:
            level = "auto" if bool(extra.get("thinking")) else "none"
        max_tokens = _as_int(
            extra.get("max_thinking_length", body.get("max_thinking_length"))
        )
    mode = level_to_thinking_mode(level)
    return ThinkingConfig(
        level=level,
        mode=mode,
        max_tokens=max_tokens,
        interleaved_history=interleaved_history,
    )


def _level_from_reasoning_object(reasoning: Any) -> Optional[ThinkingLevel]:
    if isinstance(reasoning, dict):
        if "level" in reasoning:
            level = _as_thinking_level(reasoning.get("level"))
            if level is not None:
                return level
        if "effort" in reasoning:
            level = _map_to_thinking_level(reasoning.get("effort"))
            if level is not None:
                return level
        if "mode" in reasoning:
            level = _map_to_thinking_level(reasoning.get("mode"))
            if level is not None:
                return level
        if "enabled" in reasoning:
            return "medium" if reasoning.get("enabled") else "none"
        if "type" in reasoning:
            return _map_to_thinking_level(reasoning.get("type"))
        return None
    if reasoning is not None:
        return _map_to_thinking_level(reasoning)
    return None


def _max_tokens_from_reasoning_object(reasoning: Any) -> Optional[int]:
    if not isinstance(reasoning, dict):
        return None
    for key in ("budget_tokens", "max_tokens", "max_thinking_length"):
        if key in reasoning:
            parsed = _as_int(reasoning.get(key))
            if parsed is not None:
                return parsed
    return None


def _anthropic_thinking_config(body: Dict[str, Any], extra: Dict[str, Any]) -> ThinkingConfig:
    thinking = body.get("thinking")
    interleaved_history = _parse_interleaved_history(body, extra, thinking)
    level: Optional[ThinkingLevel] = None
    max_tokens: Optional[int] = None
    if isinstance(thinking, dict):
        level = _anth_type_to_level(thinking.get("type"))
        max_tokens = _as_int(thinking.get("budget_tokens"))
    elif isinstance(thinking, bool):
        level = "medium" if thinking else "none"
    return ThinkingConfig(
        level=level,
        mode=level_to_thinking_mode(level),
        max_tokens=max_tokens if isinstance(thinking, dict) else None,
        interleaved_history=interleaved_history,
    )


def _openai_level_from_thinking_dict(
    thinking_obj: Dict[str, Any],
) -> Optional[ThinkingLevel]:
    for key in ("level", "mode"):
        level = _map_to_thinking_level(thinking_obj.get(key))
        if level is not None:
            return level
    if "type" in thinking_obj:
        level = _anth_type_to_level(thinking_obj.get("type"))
        if level is not None:
            return level
    if "effort" in thinking_obj:
        level = _map_to_thinking_level(thinking_obj.get("effort"))
        if level is not None:
            return level
    if "enabled" in thinking_obj:
        return "medium" if thinking_obj.get("enabled") else "none"
    return None


def _openai_max_tokens_from_thinking_dict(thinking_obj: Dict[str, Any]) -> Optional[int]:
    for key in ("budget_tokens", "max_tokens", "max_thinking_length"):
        if key in thinking_obj:
            parsed = _as_int(thinking_obj.get(key))
            if parsed is not None:
                return parsed
    return None


def _openai_level_from_body(body: Dict[str, Any], extra: Dict[str, Any]) -> Optional[ThinkingLevel]:
    level = _as_thinking_level(extra.get("thinking_level", body.get("thinking_level")))
    if level is not None:
        return level
    level = _map_to_thinking_level(extra.get("thinking_mode", body.get("thinking_mode")))
    if level is not None:
        return level
    if "thinking" in extra:
        return "auto" if bool(extra.get("thinking")) else "none"
    thinking = body.get("thinking")
    if thinking is not None and not isinstance(thinking, dict):
        return "auto" if bool(thinking) else "none"
    if isinstance(thinking, dict):
        return _openai_level_from_thinking_dict(thinking)
    if "reasoning_effort" in body:
        return _map_to_thinking_level(body.get("reasoning_effort"))
    if "reasoning_effort" in extra:
        return _map_to_thinking_level(extra.get("reasoning_effort"))
    level = _level_from_reasoning_object(body.get("reasoning"))
    if level is not None:
        return level
    return _level_from_reasoning_object(extra.get("reasoning"))


def _openai_thinking_config(body: Dict[str, Any], extra: Dict[str, Any]) -> ThinkingConfig:
    max_tokens = _as_int(extra.get("max_thinking_length", body.get("max_thinking_length")))
    thinking_obj = body.get("thinking")
    if isinstance(thinking_obj, dict) and max_tokens is None:
        max_tokens = _openai_max_tokens_from_thinking_dict(thinking_obj)
    if max_tokens is None:
        max_tokens = _max_tokens_from_reasoning_object(body.get("reasoning"))
    if max_tokens is None:
        max_tokens = _max_tokens_from_reasoning_object(extra.get("reasoning"))
    level = _openai_level_from_body(body, extra)
    return ThinkingConfig(
        level=level,
        mode=level_to_thinking_mode(level),
        max_tokens=max_tokens,
        interleaved_history=_parse_interleaved_history(body, extra, thinking_obj),
    )


def resolve_thinking_config(
    body: Dict[str, Any],
    *,
    extra: Optional[Dict[str, Any]] = None,
    flavor: Literal["openai", "anthropic", "entropy"] = "openai",
) -> ThinkingConfig:
    """从请求体解析 thinking_level / off-on-auto 与 max_tokens。"""
    extra = extra if extra is not None else (body.get("extra_body") or body.get("extra") or {})
    if flavor == "entropy":
        return _entropy_thinking_config(body, extra)
    if flavor == "anthropic":
        return _anthropic_thinking_config(body, extra)
    return _openai_thinking_config(body, extra)


def thinking_to_dispatch_kwargs(cfg: ThinkingConfig) -> Dict[str, Any]:
    """ThinkingConfig → gateway.dispatch 关键字参数。"""
    out: Dict[str, Any] = {
        "thinking": cfg.enabled,
        "include_thinking_in_history": cfg.interleaved_history,
    }
    level = cfg.effective_level
    mode = cfg.effective_mode
    if level is not None:
        out["thinking_level"] = level
    if mode is not None:
        out["thinking_mode"] = mode
    if cfg.max_tokens is not None:
        out["max_thinking_length"] = cfg.max_tokens
    return out


def _as_thinking_level(value: Any) -> Optional[ThinkingLevel]:
    level = normalize_thinking_level(value)
    if level in ("none", "low", "medium", "high", "xhigh", "max", "auto"):
        return level  # type: ignore[return-value]
    return None


def _anth_type_to_level(value: Any) -> Optional[ThinkingLevel]:
    if value is None:
        return None
    key = str(value).strip().lower()
    if key in ("enabled",):
        return "medium"
    if key in ("disabled",):
        return "none"
    return _map_to_thinking_level(key)


def _as_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def resolve_include_thinking_in_history(
    body: Dict[str, Any],
    *,
    extra: Optional[Dict[str, Any]] = None,
    thinking_enabled: Optional[bool] = None,
    thinking_cfg: Optional[ThinkingConfig] = None,
) -> bool:
    """解析是否将历史消息中的思考链传给下游。"""
    extra = extra if extra is not None else (body.get("extra_body") or body.get("extra") or {})

    for key in _HISTORY_FLAG_KEYS:
        if key in body:
            return bool(body[key])
        if key in extra:
            return bool(extra[key])

    if thinking_cfg is not None:
        return thinking_cfg.interleaved_history

    if thinking_enabled is not None:
        return thinking_enabled
    return False


__all__ = [
    "level_to_thinking_mode",
    "mode_to_thinking_level",
    "normalize_thinking_level",
    "normalize_thinking_mode",
    "ThinkingLevel",
    "ThinkingMode",
    "apply_thinking_history_policy",
    "extract_reasoning_text",
    "resolve_include_thinking_in_history",
    "resolve_thinking_config",
    "thinking_to_dispatch_kwargs",
]
