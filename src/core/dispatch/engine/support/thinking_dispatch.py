from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from echotools.exec.fncall.protocols.entml_thinking import (
    normalize_thinking_mode,
    parse_max_thinking_length,
)
from echotools.fncall.protocols.entml_thinking_parse import EntmlThinkingStreamFilter

from src.core.dispatch.cand import Candidate, capability_for_model


@dataclass(frozen=True)
class ThinkingDispatchPlan:
    """思考链分发：prompt 注入、adapter 原生 vs entml 解析。"""

    requester_wants_thinking: bool
    use_entml_prompt: bool
    adapter_thinking: bool
    parse_entml_thinking: bool
    prefer_adapter_thinking: bool
    thinking_mode: Optional[str] = None


def _canonical_mode(thinking_mode: Optional[str]) -> Optional[str]:
    return normalize_thinking_mode(thinking_mode)


def model_supports_thinking(candidate: Candidate, model: str) -> bool:
    known = capability_for_model(candidate, model, "thinking")
    if known is not None:
        return known
    return bool(candidate.thinking)


def resolve_thinking_mode(
    *,
    thinking: bool,
    thinking_mode: Optional[str] = None,
) -> Optional[str]:
    """解析最终思考模式：off | on | auto；未声明时返回 None。"""
    mode = _canonical_mode(thinking_mode)
    if mode is not None:
        return mode
    if thinking:
        return "auto"
    return None


def resolve_thinking_dispatch(
    *,
    thinking: bool,
    thinking_mode: Optional[str] = None,
    candidate: Candidate,
    model: str,
) -> ThinkingDispatchPlan:
    mode = resolve_thinking_mode(thinking=thinking, thinking_mode=thinking_mode)
    if mode is None:
        return ThinkingDispatchPlan(False, False, False, False, False, None)

    if mode == "off":
        return ThinkingDispatchPlan(
            requester_wants_thinking=False,
            use_entml_prompt=True,
            adapter_thinking=False,
            parse_entml_thinking=False,
            prefer_adapter_thinking=False,
            thinking_mode="off",
        )

    if mode == "on":
        return ThinkingDispatchPlan(
            requester_wants_thinking=True,
            use_entml_prompt=True,
            adapter_thinking=False,
            parse_entml_thinking=True,
            prefer_adapter_thinking=False,
            thinking_mode="on",
        )

    return ThinkingDispatchPlan(
        requester_wants_thinking=True,
        use_entml_prompt=True,
        adapter_thinking=False,
        parse_entml_thinking=True,
        prefer_adapter_thinking=False,
        thinking_mode="auto",
    )


def build_entml_protocol_options_from_plan(
    plan: ThinkingDispatchPlan,
    *,
    thinking_mode: Optional[str] = None,
    max_thinking_length: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    if not plan.use_entml_prompt:
        return None

    mode = _canonical_mode(thinking_mode) or plan.thinking_mode
    if mode is None or mode == "off":
        return None

    opts: Dict[str, Any] = {"thinking_mode": mode}
    parsed_max = parse_max_thinking_length(max_thinking_length)
    if parsed_max is not None:
        opts["max_thinking_length"] = parsed_max
    return opts


class ThinkingResponseFilter:
    """按 ThinkingDispatchPlan 路由 adapter 思考块与 entml:thinking 解析。"""

    def __init__(self, plan: ThinkingDispatchPlan) -> None:
        self._plan = plan
        self._entml = EntmlThinkingStreamFilter() if plan.parse_entml_thinking else None
        self._saw_adapter_thinking = False

    def feed(
        self, chunk: Union[str, Dict[str, Any]]
    ) -> List[Union[str, Dict[str, Any]]]:
        if not self._plan.requester_wants_thinking:
            return [chunk]

        if isinstance(chunk, dict):
            if "thinking" in chunk:
                self._saw_adapter_thinking = True
                if self._plan.adapter_thinking or self._plan.prefer_adapter_thinking:
                    return [chunk]
                return []
            return [chunk]

        if not isinstance(chunk, str):
            return [chunk]

        if not self._plan.parse_entml_thinking:
            return [chunk]

        if self._plan.prefer_adapter_thinking and self._saw_adapter_thinking:
            return [chunk]

        if self._entml is None:
            return [chunk]

        out: List[Union[str, Dict[str, Any]]] = []
        for kind, text in self._entml.feed(chunk):
            if not text:
                continue
            if kind == "thinking":
                out.append({"thinking": text})
            else:
                out.append(text)
        return out

    def finalize(self) -> List[Union[str, Dict[str, Any]]]:
        if not self._plan.parse_entml_thinking or self._entml is None:
            return []
        if self._plan.prefer_adapter_thinking and self._saw_adapter_thinking:
            return []

        out: List[Union[str, Dict[str, Any]]] = []
        for kind, text in self._entml.finalize():
            if not text:
                continue
            if kind == "thinking":
                out.append({"thinking": text})
            else:
                out.append(text)
        return out
