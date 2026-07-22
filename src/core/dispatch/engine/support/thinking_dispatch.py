from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from echotools.fncall.protocols.entml_thinking_parse import EntmlThinkingStreamFilter

from src.core.dispatch.cand import Candidate, capability_for_model


@dataclass(frozen=True)
class ThinkingDispatchPlan:
    """思考链分发：adapter 原生 vs entml prompt/解析。"""

    requester_wants_thinking: bool
    use_entml_prompt: bool
    adapter_thinking: bool
    parse_entml_thinking: bool
    prefer_adapter_thinking: bool


def _normalize_mode(thinking_mode: Optional[str]) -> str:
    return str(thinking_mode or "").strip().lower()


def model_supports_thinking(candidate: Candidate, model: str) -> bool:
    known = capability_for_model(candidate, model, "thinking")
    if known is not None:
        return known
    return bool(candidate.thinking)


def requester_wants_thinking(
    thinking: bool,
    thinking_mode: Optional[str] = None,
) -> bool:
    mode = _normalize_mode(thinking_mode)
    if mode in ("disabled", "off", "false"):
        return False
    if thinking:
        return True
    return mode in ("interleaved", "auto", "enabled", "on", "thinking")


def resolve_thinking_dispatch(
    *,
    thinking: bool,
    thinking_mode: Optional[str] = None,
    candidate: Candidate,
    model: str,
) -> ThinkingDispatchPlan:
    wants = requester_wants_thinking(thinking, thinking_mode)
    if not wants:
        return ThinkingDispatchPlan(False, False, False, False, False)

    mode = _normalize_mode(thinking_mode)
    auto = mode == "auto"
    supports = model_supports_thinking(candidate, model)

    if auto:
        return ThinkingDispatchPlan(
            requester_wants_thinking=True,
            use_entml_prompt=True,
            adapter_thinking=False,
            parse_entml_thinking=True,
            prefer_adapter_thinking=True,
        )

    if supports:
        return ThinkingDispatchPlan(
            requester_wants_thinking=True,
            use_entml_prompt=False,
            adapter_thinking=True,
            parse_entml_thinking=False,
            prefer_adapter_thinking=True,
        )

    return ThinkingDispatchPlan(
        requester_wants_thinking=True,
        use_entml_prompt=True,
        adapter_thinking=False,
        parse_entml_thinking=True,
        prefer_adapter_thinking=False,
    )


def build_entml_protocol_options_from_plan(
    plan: ThinkingDispatchPlan,
    *,
    thinking_mode: Optional[str] = None,
    max_thinking_length: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    if not plan.use_entml_prompt:
        return None

    opts: Dict[str, Any] = {}
    mode = _normalize_mode(thinking_mode)
    if mode:
        opts["thinking_mode"] = mode
    elif plan.prefer_adapter_thinking:
        opts["thinking_mode"] = "auto"
    else:
        opts["thinking_mode"] = "interleaved"
    if max_thinking_length is not None:
        opts["max_thinking_length"] = int(max_thinking_length)
    return opts or None


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
