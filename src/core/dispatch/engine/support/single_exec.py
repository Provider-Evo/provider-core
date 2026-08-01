"""单候选项执行逻辑。"""

from __future__ import annotations

import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from echotools.fncall.parsers.stream import FncallStreamParser

from src.core.dispatch.cand import Candidate
from src.core.dispatch.engine.support.fncall_context import (
    FncallStreamEmitState,
    feed_fncall_stream,
    finalize_fncall_stream,
    native_complete_kw,
    prepare_worker_messages,
)
from src.core.dispatch.engine.support.thinking_dispatch import ThinkingResponseFilter
from src.core.utils.errors import ProviderError
from src.core.utils.errors.http_errors import maybe_classify_exception
from src.foundation.logger import get_logger

logger = get_logger(__name__)


class SingleExecState:
    """单候选项执行过程中的可变统计状态。"""

    __slots__ = ("start", "ft", "tc", "ok", "p_usage", "acc_len", "fncall_emit")

    def __init__(self) -> None:
        self.start = time.monotonic()
        self.ft: Optional[float] = None
        self.tc = 0
        self.ok = False
        self.p_usage: Optional[Dict] = None
        self.acc_len = 0
        self.fncall_emit = FncallStreamEmitState()


def _note_text_chunk(state: SingleExecState, text: str) -> None:
    state.acc_len += len(text)
    if state.ft is None:
        state.ft = time.monotonic()


async def _yield_fncall_items(
    fp: FncallStreamParser,
    text: str,
    state: SingleExecState,
) -> AsyncGenerator[Union[str, Dict], None]:
    for item in feed_fncall_stream(fp, text, state.fncall_emit):
        if isinstance(item, str):
            state.tc += 1
            _note_text_chunk(state, item)
            yield item
        else:
            yield item


async def _yield_str_chunk(
    chunk: str,
    fp: Optional[FncallStreamParser],
    thinking_filter: Optional[ThinkingResponseFilter],
    state: SingleExecState,
) -> AsyncGenerator[Union[str, Dict], None]:
    if thinking_filter is None:
        if fp is None:
            state.tc += 1
            _note_text_chunk(state, chunk)
            yield chunk
            return
        async for item in _yield_fncall_items(fp, chunk, state):
            yield item
        return
    for item in thinking_filter.feed(chunk):
        if not isinstance(item, str):
            yield item
            continue
        if fp is None:
            state.tc += 1
            _note_text_chunk(state, item)
            yield item
            continue
        async for parsed in _yield_fncall_items(fp, item, state):
            yield parsed


async def _yield_dict_chunk(
    chunk: Dict[str, Any],
    thinking_filter: Optional[ThinkingResponseFilter],
    state: SingleExecState,
) -> AsyncGenerator[Union[str, Dict], None]:
    if "usage" in chunk:
        state.p_usage = chunk["usage"]
        return
    if thinking_filter is None:
        yield chunk
        return
    for item in thinking_filter.feed(chunk):
        yield item


async def _stream_single_chunks(
    adapter: Any,
    cand: Candidate,
    worker_msgs: List[Dict],
    model: str,
    stream: bool,
    adapter_thinking: bool,
    search: bool,
    complete_kw: Dict[str, Any],
    fp: Optional[FncallStreamParser],
    thinking_filter: Optional[ThinkingResponseFilter],
    state: SingleExecState,
    ) -> AsyncGenerator[Union[str, Dict], None]:
    async for chunk in adapter.complete(
        cand,
        worker_msgs,
        model,
        stream,
        thinking=adapter_thinking,
        search=search,
        **complete_kw,
    ):
        if isinstance(chunk, str):
            async for item in _yield_str_chunk(chunk, fp, thinking_filter, state):
                yield item
        elif isinstance(chunk, dict):
            async for item in _yield_dict_chunk(chunk, thinking_filter, state):
                yield item


def _build_single_exec_plan(
    reg: Any,
    cand: Candidate,
    msgs: List[Dict],
    tools: Optional[List[Dict]],
    model: str,
    fncall_lang: str,
    protocol_id: str,
    thinking: bool,
    kw: Dict[str, Any],
) -> tuple[Any, List[Dict], Optional[Any], Optional[FncallStreamParser], Optional[ThinkingResponseFilter], bool]:
    adapter = reg.adapter_for(cand)
    if not adapter:
        raise ProviderError("无适配器: {}".format(cand.platform))
    worker_msgs, protocol, plan = prepare_worker_messages(
        msgs,
        tools,
        cand,
        model=model,
        fncall_lang=fncall_lang,
        protocol_id=protocol_id,
        thinking=thinking,
        thinking_level=kw.get("thinking_level"),
        thinking_mode=kw.get("thinking_mode"),
        max_thinking_length=kw.get("max_thinking_length"),
        include_thinking_in_history=kw.get("include_thinking_in_history"),
    )
    native = cand.native_tools
    fp = (
        FncallStreamParser(tools=tools, protocol=protocol)
        if tools and not native
        else None
    )
    thinking_filter = (
        ThinkingResponseFilter(plan) if plan.requester_wants_thinking else None
    )
    return adapter, worker_msgs, fp, thinking_filter, plan, plan.adapter_thinking


async def _record_single_result(
    reg: Any, cand: Candidate, state: SingleExecState
) -> None:
    dur = time.monotonic() - state.start
    lat = (state.ft - state.start) if state.ft else dur
    gen_dur = (time.monotonic() - state.ft) if state.ft else dur
    comp_tok = int(state.p_usage.get("completion_tokens", 0)) if state.p_usage else 0
    await reg.selector.record(
        cand.id,
        state.ok,
        latency=lat,
        tokens=state.tc,
        duration=dur,
        generation_dur=gen_dur,
        completion_tokens=comp_tok,
        platform=cand.platform,
    )
    from src.core.dispatch.circuit import get_platform_circuit_breaker

    get_platform_circuit_breaker().record(cand.platform, state.ok)


async def _yield_single_tail(
    fp: Optional[FncallStreamParser],
    prompt_len: int,
    state: SingleExecState,
    thinking_filter: Optional[ThinkingResponseFilter],
) -> AsyncGenerator[Union[str, Dict], None]:
    from src.core.dispatch.engine.execs import _usage_for_response

    if thinking_filter is not None:
        for item in thinking_filter.finalize():
            if isinstance(item, str) and fp is not None:
                async for parsed in _yield_fncall_items(fp, item, state):
                    yield parsed
            else:
                yield item

    if fp is not None:
        for item in finalize_fncall_stream(fp, state.fncall_emit):
            if isinstance(item, str):
                state.tc += 1
                _note_text_chunk(state, item)
            yield item
    yield {"usage": _usage_for_response(prompt_len, state.acc_len, state.p_usage)}
    state.ok = True


async def single_execute(
    reg: Any,
    cand: Candidate,
    msgs: List[Dict],
    model: str,
    stream: bool,
    thinking: bool,
    search: bool,
    tools: Optional[List[Dict]],
    prompt_len: int,
    fncall_lang: str = "en",
    protocol_id: str = "",
    **kw: Any,
) -> AsyncGenerator[Union[str, Dict], None]:
    """单候选项执行。"""
    adapter, worker_msgs, fp, thinking_filter, plan, adapter_thinking = _build_single_exec_plan(
        reg, cand, msgs, tools, model, fncall_lang, protocol_id, thinking, kw
    )
    _ = plan
    state = SingleExecState()
    yield {"_meta": {"platform": cand.platform}}
    complete_kw = native_complete_kw(kw, tools, cand.native_tools)
    try:
        async for chunk in _stream_single_chunks(
            adapter,
            cand,
            worker_msgs,
            model,
            stream,
            adapter_thinking,
            search,
            complete_kw,
            fp,
            thinking_filter,
            state,
        ):
            yield chunk
        async for tail in _yield_single_tail(fp, prompt_len, state, thinking_filter):
            yield tail
    except Exception as exc:
        raise maybe_classify_exception(exc)
    finally:
        await _record_single_result(reg, cand, state)
