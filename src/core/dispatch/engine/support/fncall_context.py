
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

from echotools.exec.fncall.parsers.stream import FncallStreamParser

from src.core.fncall.prompt.inject import inject_fncall
from src.core.fncall.reg import get_protocol

from .thinking_dispatch import ThinkingDispatchPlan, resolve_thinking_dispatch


def fold_system_into_user(
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """无 tools 时将 system 消息合并进首条 user 消息。"""
    if tools:
        return messages
    sys_parts: List[str] = []
    non_sys: List[Dict[str, Any]] = []
    for msg in messages:
        if msg.get("role") == "system":
            content = msg.get("content", "")
            if content:
                sys_parts.append(content if isinstance(content, str) else str(content))
        else:
            non_sys.append(msg)
    if not sys_parts:
        return messages
    sys_text = "\n\n".join(sys_parts)
    merged = list(non_sys)
    for idx, msg in enumerate(merged):
        if msg.get("role") == "user":
            old = msg.get("content", "")
            old_text = old if isinstance(old, str) else str(old)
            merged[idx] = {**msg, "content": sys_text + "\n\n" + old_text}
            return merged
    merged.insert(0, {"role": "user", "content": sys_text})
    return merged


def build_dispatch_extra_kw(
    kw: Dict[str, Any],
    *,
    upload_files: Optional[List[Any]],
    temperature: Optional[float],
    top_p: Optional[float],
    max_tokens: Optional[int],
    stop: Optional[List[str]],
) -> Dict[str, Any]:
    """组装 dispatch 透传关键字参数。"""
    extra_kw: Dict[str, Any] = dict(kw)
    extra_kw.pop("fncall_lang", None)
    extra_kw.pop("protocol_id", None)
    if upload_files:
        extra_kw["upload_files"] = upload_files
    if temperature is not None:
        extra_kw["temperature"] = temperature
    if top_p is not None:
        extra_kw["top_p"] = top_p
    if max_tokens is not None:
        extra_kw["max_tokens"] = max_tokens
    if stop:
        extra_kw["stop"] = stop
    return extra_kw


def fncall_lang(kw: Dict[str, Any]) -> str:
    raw = kw.get("fncall_lang", "en")
    return raw if raw in ("en", "zh") else "en"


def resolve_protocol(*, protocol_id: str, platform_id: str = "") -> Any:
    if protocol_id:
        return get_protocol(protocol_id=protocol_id)
    return get_protocol(platform_id=platform_id)


def build_entml_protocol_options(
    *,
    thinking: bool = False,
    thinking_level: Optional[str] = None,
    thinking_mode: Optional[str] = None,
    max_thinking_length: Optional[int] = None,
    plan: Optional[ThinkingDispatchPlan] = None,
    include_thinking_in_history: Optional[bool] = None,
) -> Optional[Dict[str, Any]]:
    _ = (
        thinking,
        thinking_level,
        thinking_mode,
        max_thinking_length,
        plan,
        include_thinking_in_history,
    )
    return None


def _inject_worker_messages(
    msgs: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]],
    cand: Any,
    *,
    protocol_id: str,
    fncall_lang: str,
    dump_prompt: bool,
    native: bool,
) -> Tuple[List[Dict[str, Any]], Optional[Any]]:
    if not tools or native:
        return msgs, None
    protocol = resolve_protocol(protocol_id=protocol_id, platform_id=cand.platform)
    worker_msgs = inject_fncall(
        msgs,
        tools,
        protocol,
        lang=fncall_lang,
        dump_prompt=dump_prompt,
        protocol_options=None,
    )
    return worker_msgs, protocol


def prepare_worker_messages(
    msgs: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]],
    cand: Any,
    *,
    model: str = "",
    fncall_lang: str = "en",
    protocol_id: str = "",
    dump_prompt: bool = False,
    thinking: bool = False,
    thinking_level: Optional[str] = None,
    thinking_mode: Optional[str] = None,
    max_thinking_length: Optional[int] = None,
    include_thinking_in_history: Optional[bool] = None,
) -> Tuple[List[Dict[str, Any]], Optional[Any], ThinkingDispatchPlan]:
    """按平台解析协议并注入工具定义；native_tools 平台直接透传 messages。"""
    _ = (max_thinking_length, include_thinking_in_history)
    plan = resolve_thinking_dispatch(
        thinking=thinking,
        thinking_mode=thinking_mode,
        thinking_level=thinking_level,
        candidate=cand,
        model=model,
    )
    worker_msgs, protocol = _inject_worker_messages(
        msgs,
        tools,
        cand,
        protocol_id=protocol_id,
        fncall_lang=fncall_lang,
        dump_prompt=dump_prompt,
        native=cand.native_tools,
    )
    return worker_msgs, protocol, plan


def dump_race_prompt(
    msgs: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]],
    cands: List[Any],
    *,
    model: str = "",
    fncall_lang: str = "en",
    protocol_id: str = "",
    thinking: bool = False,
    thinking_level: Optional[str] = None,
    thinking_mode: Optional[str] = None,
    max_thinking_length: Optional[int] = None,
) -> None:
    """竞速 worker 启动前统一转储一次 prompt，避免 N 个 worker 各写一份。"""
    _ = (model, thinking, thinking_level, thinking_mode, max_thinking_length)
    if not tools or not cands:
        return
    if any(c.native_tools for c in cands):
        return
    protocol = resolve_protocol(protocol_id=protocol_id, platform_id=cands[0].platform)
    inject_fncall(
        msgs,
        tools,
        protocol,
        lang=fncall_lang,
        dump_prompt=True,
        protocol_options=None,
    )


def native_complete_kw(
    kw: Dict[str, Any],
    tools: Optional[List[Dict[str, Any]]],
    native: bool,
) -> Dict[str, Any]:
    if not (native and tools):
        return kw
    complete_kw: Dict[str, Any] = dict(kw)
    complete_kw["tools"] = tools
    tool_choice = kw.get("tool_choice")
    if tool_choice is not None:
        complete_kw["tool_choice"] = tool_choice
    return complete_kw


@dataclass
class FncallStreamEmitState:
    last_partial_len: int = 0


def feed_fncall_stream(
    fp: FncallStreamParser,
    text: str,
    state: FncallStreamEmitState,
) -> List[Union[str, Dict[str, Any]]]:
    if not text:
        return []
    fp.feed(text)
    return _collect_fncall_parser_output(fp, state)


def finalize_fncall_stream(
    fp: FncallStreamParser,
    state: FncallStreamEmitState,
) -> List[Union[str, Dict[str, Any]]]:
    out: List[Union[str, Dict[str, Any]]] = []
    partial = fp.partial_text
    if len(partial) > state.last_partial_len:
        out.append(partial[state.last_partial_len :])
        state.last_partial_len = len(partial)
    ready = fp.get_ready_tool_calls()
    if ready:
        out.append({"tool_calls": ready})
        return out
    if fp.has_calls:
        _, calls = fp.finalize()
        ready = fp.get_ready_tool_calls()
        if ready:
            out.append({"tool_calls": ready})
        elif calls:
            out.append({"tool_calls": calls})
    return out


def _collect_fncall_parser_output(
    fp: FncallStreamParser,
    state: FncallStreamEmitState,
) -> List[Union[str, Dict[str, Any]]]:
    out: List[Union[str, Dict[str, Any]]] = []
    partial = fp.partial_text
    if len(partial) > state.last_partial_len:
        out.append(partial[state.last_partial_len :])
        state.last_partial_len = len(partial)
    ready = fp.get_ready_tool_calls()
    if ready:
        out.append({"tool_calls": ready})
    return out
