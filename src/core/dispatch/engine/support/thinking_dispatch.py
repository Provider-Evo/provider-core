from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from src.core.dispatch.cand import Candidate, capability_for_model
from src.routes.shared.thinking import (
    level_to_thinking_mode,
    mode_to_thinking_level,
    normalize_thinking_level,
    normalize_thinking_mode,
)


@dataclass(frozen=True)
class ThinkingDispatchPlan:
    """思考链分发：仅 adapter 原生 thinking，不注入 entml 提示、不解析 entml 标签。"""

    requester_wants_thinking: bool
    adapter_thinking: bool
    thinking_mode: Optional[str] = None
    thinking_level: Optional[str] = None


def _resolve_level(
    thinking_level: Optional[str] = None,
    thinking_mode: Optional[str] = None,
) -> Optional[str]:
    level = normalize_thinking_level(thinking_level)
    if level is not None:
        return level
    return mode_to_thinking_level(normalize_thinking_mode(thinking_mode))


def model_supports_thinking(candidate: Candidate, model: str) -> bool:
    known = capability_for_model(candidate, model, "thinking")
    if known is not None:
        return known
    return bool(candidate.thinking)


def resolve_thinking_mode(
    *,
    thinking: bool,
    thinking_mode: Optional[str] = None,
    thinking_level: Optional[str] = None,
) -> Optional[str]:
    """解析最终思考模式：off | on | auto；未声明时返回 None。"""
    level = _resolve_level(thinking_level, thinking_mode)
    if level is not None:
        return level_to_thinking_mode(level)
    if thinking:
        return "auto"
    return None


def resolve_thinking_dispatch(
    *,
    thinking: bool,
    thinking_mode: Optional[str] = None,
    thinking_level: Optional[str] = None,
    candidate: Candidate,
    model: str,
) -> ThinkingDispatchPlan:
    level = _resolve_level(thinking_level, thinking_mode)
    mode = resolve_thinking_mode(
        thinking=thinking,
        thinking_mode=thinking_mode,
        thinking_level=thinking_level,
    )
    if mode is None and level is None:
        return ThinkingDispatchPlan(False, False, None, None)

    if mode == "off" or level == "none":
        return ThinkingDispatchPlan(
            requester_wants_thinking=False,
            adapter_thinking=False,
            thinking_mode="off",
            thinking_level="none",
        )

    resolved_level = level or ("medium" if mode == "on" else "auto")
    resolved_mode = mode or level_to_thinking_mode(resolved_level)
    wants = True
    adapter_thinking = wants and (
        model_supports_thinking(candidate, model) or mode in ("on", "auto") or thinking
    )
    return ThinkingDispatchPlan(
        requester_wants_thinking=wants,
        adapter_thinking=adapter_thinking,
        thinking_mode=resolved_mode,
        thinking_level=resolved_level,
    )


def build_entml_protocol_options_from_plan(
    plan: ThinkingDispatchPlan,
    *,
    thinking_level: Optional[str] = None,
    thinking_mode: Optional[str] = None,
    max_thinking_length: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    _ = (plan, thinking_level, thinking_mode, max_thinking_length)
    return None


class ThinkingResponseFilter:
    """透传 adapter 思考块；不做 entml:thinking 标签解析。"""

    def __init__(self, plan: ThinkingDispatchPlan) -> None:
        self._plan = plan

    def feed(
        self, chunk: Union[str, Dict[str, Any]]
    ) -> List[Union[str, Dict[str, Any]]]:
        if not self._plan.requester_wants_thinking:
            return [chunk]
        return [chunk]

    def finalize(self) -> List[Union[str, Dict[str, Any]]]:
        return []
