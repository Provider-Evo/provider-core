from __future__ import annotations

"""思考链（reasoning / thinking）历史回传与请求解析。"""

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

from echotools.exec.fncall.protocols.entml_thinking import normalize_thinking_mode
from echotools.exec.fncall.protocols.entml_thinking_history import (
    apply_thinking_history_policy,
    extract_reasoning_text,
    parse_interleaved_history,
)

ThinkingMode = Literal["off", "on", "auto"]


@dataclass(frozen=True)
class ThinkingConfig:
    """Entropy 规范思考配置。

    interleaved_history: 交错历史开关（非 mode）。
    - True: 把历史 assistant 的思考+回复一并传给模型
    - False: 只传可见回复，剥离思考链
    """

    mode: Optional[ThinkingMode] = None
    max_tokens: Optional[int] = None
    interleaved_history: bool = False

    @property
    def enabled(self) -> bool:
        return self.mode in ("on", "auto")


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


def _entropy_thinking_config(
    body: Dict[str, Any],
    extra: Dict[str, Any],
) -> ThinkingConfig:
    thinking = body.get("thinking")
    mode: Optional[ThinkingMode] = None
    max_tokens: Optional[int] = None
    interleaved_history = _parse_interleaved_history(body, extra, thinking)
    if isinstance(thinking, dict):
        mode = _as_thinking_mode(thinking.get("mode"))
        max_tokens = _as_int(thinking.get("max_tokens"))
    elif thinking is not None:
        mode = _as_thinking_mode(thinking)
    else:
        raw_mode = extra.get("thinking_mode", body.get("thinking_mode"))
        mode = _as_thinking_mode(raw_mode)
        if mode is None and "thinking" in extra:
            mode = "auto" if bool(extra.get("thinking")) else "off"
        max_tokens = _as_int(
            extra.get("max_thinking_length", body.get("max_thinking_length"))
        )
    return ThinkingConfig(
        mode=mode,
        max_tokens=max_tokens,
        interleaved_history=interleaved_history,
    )


def resolve_thinking_config(
    body: Dict[str, Any],
    *,
    extra: Optional[Dict[str, Any]] = None,
    flavor: Literal["openai", "anthropic", "entropy"] = "openai",
) -> ThinkingConfig:
    """从请求体解析 off / on / auto 与 max_tokens。"""
    extra = extra if extra is not None else (body.get("extra_body") or body.get("extra") or {})
    max_tokens: Optional[int] = None
    mode: Optional[ThinkingMode] = None

    if flavor == "entropy":
        return _entropy_thinking_config(body, extra)

    if flavor == "anthropic":
        thinking = body.get("thinking")
        interleaved_history = _parse_interleaved_history(body, extra, thinking)
        if isinstance(thinking, dict):
            mode = _anth_type_to_mode(thinking.get("type"))
            max_tokens = _as_int(thinking.get("budget_tokens"))
        elif isinstance(thinking, bool):
            mode = "on" if thinking else "off"
        else:
            mode = None
            max_tokens = None
        return ThinkingConfig(
            mode=mode,
            max_tokens=max_tokens if isinstance(thinking, dict) else None,
            interleaved_history=interleaved_history,
        )

    raw_mode = extra.get("thinking_mode", body.get("thinking_mode"))
    mode = _as_thinking_mode(raw_mode)
    max_tokens = _as_int(extra.get("max_thinking_length", body.get("max_thinking_length")))
    if mode is None:
        if "thinking" in extra:
            mode = "auto" if bool(extra.get("thinking")) else "off"
        elif "thinking" in body and not isinstance(body.get("thinking"), dict):
            mode = "auto" if bool(body.get("thinking")) else "off"
    interleaved_history = _parse_interleaved_history(body, extra, body.get("thinking"))
    return ThinkingConfig(
        mode=mode,
        max_tokens=max_tokens,
        interleaved_history=interleaved_history,
    )


def thinking_to_dispatch_kwargs(cfg: ThinkingConfig) -> Dict[str, Any]:
    """ThinkingConfig → gateway.dispatch 关键字参数。"""
    out: Dict[str, Any] = {
        "thinking": cfg.enabled,
    }
    if cfg.mode is not None:
        out["thinking_mode"] = cfg.mode
    if cfg.max_tokens is not None:
        out["max_thinking_length"] = cfg.max_tokens
    return out


def _as_thinking_mode(value: Any) -> Optional[ThinkingMode]:
    mode = normalize_thinking_mode(value)
    if mode in ("off", "on", "auto"):
        return mode  # type: ignore[return-value]
    return None


def _anth_type_to_mode(value: Any) -> Optional[ThinkingMode]:
    if value is None:
        return None
    key = str(value).strip().lower()
    if key in ("enabled",):
        return "on"
    if key in ("disabled",):
        return "off"
    return _as_thinking_mode(key)


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
    """解析是否将历史消息中的思考链传给下游。

    显式参数优先；否则使用 thinking_cfg.interleaved_history；
    再回退到 thinking_enabled。
    """
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
    "ThinkingConfig",
    "ThinkingMode",
    "apply_thinking_history_policy",
    "extract_reasoning_text",
    "resolve_include_thinking_in_history",
    "resolve_thinking_config",
    "thinking_to_dispatch_kwargs",
]
