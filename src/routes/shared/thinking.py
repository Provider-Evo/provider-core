from __future__ import annotations

"""思考链（reasoning / thinking）历史回传与请求解析。"""

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

from echotools.exec.fncall.protocols.entml_thinking import (
    normalize_thinking_level,
    normalize_thinking_mode,
)
from echotools.exec.fncall.protocols.entml_thinking_history import (
    apply_thinking_history_policy,
    extract_reasoning_text,
    parse_interleaved_history,
)

ThinkingMode = Literal["off", "on", "auto"]
ThinkingLevel = Literal["none", "low", "medium", "high", "xhigh", "max", "auto"]

_LEVEL_ALIASES = {
    "minimal": "low",
    "default": "medium",
}


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


def resolve_thinking_config(
    body: Dict[str, Any],
    *,
    extra: Optional[Dict[str, Any]] = None,
    flavor: Literal["openai", "anthropic", "entropy"] = "openai",
) -> ThinkingConfig:
    """从请求体解析 thinking_level / off-on-auto 与 max_tokens。"""
    extra = extra if extra is not None else (body.get("extra_body") or body.get("extra") or {})
    max_tokens: Optional[int] = None
    level: Optional[ThinkingLevel] = None

    if flavor == "entropy":
        return _entropy_thinking_config(body, extra)

    if flavor == "anthropic":
        thinking = body.get("thinking")
        interleaved_history = _parse_interleaved_history(body, extra, thinking)
        if isinstance(thinking, dict):
            level = _anth_type_to_level(thinking.get("type"))
            max_tokens = _as_int(thinking.get("budget_tokens"))
        elif isinstance(thinking, bool):
            level = "medium" if thinking else "none"
        mode = level_to_thinking_mode(level)
        return ThinkingConfig(
            level=level,
            mode=mode,
            max_tokens=max_tokens if isinstance(thinking, dict) else None,
            interleaved_history=interleaved_history,
        )

    level = _as_thinking_level(extra.get("thinking_level", body.get("thinking_level")))
    max_tokens = _as_int(extra.get("max_thinking_length", body.get("max_thinking_length")))
    if level is None:
        level = _map_to_thinking_level(extra.get("thinking_mode", body.get("thinking_mode")))
    if level is None:
        if "thinking" in extra:
            level = "auto" if bool(extra.get("thinking")) else "none"
        elif "thinking" in body and not isinstance(body.get("thinking"), dict):
            level = "auto" if bool(body.get("thinking")) else "none"
        elif isinstance(body.get("thinking"), dict):
            thinking_obj = body.get("thinking") or {}
            level = _map_to_thinking_level(thinking_obj.get("level"))
            if level is None:
                level = _map_to_thinking_level(thinking_obj.get("mode"))
            if level is None and "type" in thinking_obj:
                level = _anth_type_to_level(thinking_obj.get("type"))
            if level is None and "effort" in thinking_obj:
                level = _map_to_thinking_level(thinking_obj.get("effort"))
            if level is None and "enabled" in thinking_obj:
                level = "medium" if thinking_obj.get("enabled") else "none"
            if max_tokens is None:
                for key in ("budget_tokens", "max_tokens", "max_thinking_length"):
                    if key in thinking_obj:
                        max_tokens = _as_int(thinking_obj.get(key))
                        if max_tokens is not None:
                            break

    if level is None and "reasoning_effort" in body:
        level = _map_to_thinking_level(body.get("reasoning_effort"))
    if level is None and "reasoning_effort" in extra:
        level = _map_to_thinking_level(extra.get("reasoning_effort"))

    if level is None:
        level = _level_from_reasoning_object(body.get("reasoning"))
    if level is None:
        level = _level_from_reasoning_object(extra.get("reasoning"))
    if max_tokens is None:
        max_tokens = _max_tokens_from_reasoning_object(body.get("reasoning"))
    if max_tokens is None:
        max_tokens = _max_tokens_from_reasoning_object(extra.get("reasoning"))

    interleaved_history = _parse_interleaved_history(body, extra, body.get("thinking"))
    mode = level_to_thinking_mode(level)
    return ThinkingConfig(
        level=level,
        mode=mode,
        max_tokens=max_tokens,
        interleaved_history=interleaved_history,
    )


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
    "ThinkingLevel",
    "ThinkingMode",
    "apply_thinking_history_policy",
    "extract_reasoning_text",
    "resolve_include_thinking_in_history",
    "resolve_thinking_config",
    "thinking_to_dispatch_kwargs",
]
