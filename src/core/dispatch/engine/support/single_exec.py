"""单候选项执行逻辑。"""

from __future__ import annotations

import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from echotools.fncall.parsers.stream import FncallStreamParser

from src.core.dispatch.cand import Candidate
from src.core.dispatch.engine.support.fncall_context import (
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

    __slots__ = ("start", "ft", "tc", "ok", "p_usage", "acc_len")

    def __init__(self) -> None:
        self.start = time.monotonic()
        self.ft: Optional[float] = None
        self.tc = 0
        self.ok = False
        self.p_usage: Optional[Dict] = None
        self.acc_len = 0


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
            state.tc += 1
            if thinking_filter is not None:
                for item in thinking_filter.feed(chunk):
                    if isinstance(item, str):
                        state.acc_len += len(item)
                        if state.ft is None:
                            state.ft = time.monotonic()
                        if fp:
                            fp.feed(item)
                    yield item
                continue
            state.acc_len += len(chunk)
            if state.ft is None:
                state.ft = time.monotonic()
            if fp:
                fp.feed(chunk)
            yield chunk
        elif isinstance(chunk, dict):
            if "usage" in chunk:
                state.p_usage = chunk["usage"]
            elif thinking_filter is not None:
                for item in thinking_filter.feed(chunk):
                    yield item
            else:
                yield chunk


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
            if isinstance(item, str) and fp:
                fp.feed(item)
            yield item

    if fp and fp.has_calls:
        _, calls = fp.finalize()
        if calls:
            yield {"tool_calls": calls}
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
        thinking_mode=kw.get("thinking_mode"),
        max_thinking_length=kw.get("max_thinking_length"),
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
    state = SingleExecState()
    yield {"_meta": {"platform": cand.platform}}
    complete_kw = native_complete_kw(kw, tools, native)
    try:
        async for chunk in _stream_single_chunks(
            adapter,
            cand,
            worker_msgs,
            model,
            stream,
            plan.adapter_thinking,
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
