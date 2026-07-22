
from typing import Any, Dict, List, Optional, Tuple

from src.core.fncall.prompt.inject import inject_fncall
from src.core.fncall.reg import get_protocol

from .thinking_dispatch import (
    ThinkingDispatchPlan,
    build_entml_protocol_options_from_plan,
    resolve_thinking_dispatch,
)


def build_entml_protocol_options(
    *,
    thinking: bool = False,
    thinking_mode: Optional[str] = None,
    max_thinking_length: Optional[int] = None,
    plan: Optional[ThinkingDispatchPlan] = None,
) -> Optional[Dict[str, Any]]:
    """从 dispatch 参数构建 entml protocol_options；无声明时返回 None。"""
    if plan is not None:
        return build_entml_protocol_options_from_plan(
            plan,
            thinking_mode=thinking_mode,
            max_thinking_length=max_thinking_length,
        )

    opts: Dict[str, Any] = {}
    if thinking_mode is not None:
        mode = str(thinking_mode).strip()
        if mode:
            opts["thinking_mode"] = mode
    elif thinking:
        opts["thinking_mode"] = "interleaved"
    if max_thinking_length is not None:
        opts["max_thinking_length"] = int(max_thinking_length)
    return opts or None


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
    thinking_mode: Optional[str] = None,
    max_thinking_length: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], Optional[Any], ThinkingDispatchPlan]:
    """按平台解析协议并注入工具定义；native_tools 平台直接透传 messages。"""
    plan = resolve_thinking_dispatch(
        thinking=thinking,
        thinking_mode=thinking_mode,
        candidate=cand,
        model=model,
    )
    native = cand.native_tools
    if not tools or native:
        return msgs, None, plan
    protocol = resolve_protocol(protocol_id=protocol_id, platform_id=cand.platform)
    protocol_options = build_entml_protocol_options(
        thinking=thinking,
        thinking_mode=thinking_mode,
        max_thinking_length=max_thinking_length,
        plan=plan,
    )
    worker_msgs = inject_fncall(
        msgs,
        tools,
        protocol,
        lang=fncall_lang,
        dump_prompt=dump_prompt,
        protocol_options=protocol_options,
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
    thinking_mode: Optional[str] = None,
    max_thinking_length: Optional[int] = None,
) -> None:
    """竞速 worker 启动前统一转储一次 prompt，避免 N 个 worker 各写一份。"""
    if not tools or not cands:
        return
    if any(c.native_tools for c in cands):
        return
    protocol = resolve_protocol(protocol_id=protocol_id, platform_id=cands[0].platform)
    plan = resolve_thinking_dispatch(
        thinking=thinking,
        thinking_mode=thinking_mode,
        candidate=cands[0],
        model=model,
    )
    protocol_options = build_entml_protocol_options(
        thinking=thinking,
        thinking_mode=thinking_mode,
        max_thinking_length=max_thinking_length,
        plan=plan,
    )
    inject_fncall(
        msgs,
        tools,
        protocol,
        lang=fncall_lang,
        dump_prompt=True,
        protocol_options=protocol_options,
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
