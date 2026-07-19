from __future__ import annotations

import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from echotools.dispatch.usage import fallback_usage as _fallback_usage
from echotools.dispatch.usage import normalize_usage as _normalize_usage
from echotools.fncall.parsers.stream import FncallStreamParser

from src.core.dispatch.cand import Candidate
from src.core.dispatch.engine.race_worker import race_execute
from src.core.dispatch.engine.support.fncall_context import (
    native_complete_kw,
    prepare_worker_messages,
)
from src.core.utils.errors import ProviderError
from src.core.utils.errors.http_errors import maybe_classify_exception
from src.foundation.config import get_config
from src.foundation.logger import get_logger

__all__ = ["single_execute", "race_execute", "record_candidate", "run_selected"]

logger = get_logger(__name__)


class _RespLenProxy:
    """usage 辅助函数仅调用 len(resp_text)，用整数长度代理即可。"""

    __slots__ = ("_length",)

    def __init__(self, length: int) -> None:
        self._length = length

    def __len__(self) -> int:
        return self._length


def _usage_for_response(
    prompt_len: int,
    resp_len: int,
    raw_usage: Optional[Dict[str, Any]] = None,
) -> Dict[str, int]:
    proxy = _RespLenProxy(resp_len)
    if raw_usage:
        return _normalize_usage(raw_usage, prompt_len, proxy)
    return _fallback_usage(prompt_len, proxy)


def _cancel_race_workers(
    infos: List[Dict[str, Any]], *, skip: Optional[Dict] = None
) -> None:
    for info in infos:
        if info is skip:
            continue
        info["ev"].set()
        task = info["task"]
        if not task.done():
            task.cancel()


class _SingleExecState:
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
    thinking: bool,
    search: bool,
    complete_kw: Dict[str, Any],
    fp: Optional[FncallStreamParser],
    state: _SingleExecState,
) -> AsyncGenerator[Union[str, Dict], None]:
    async for chunk in adapter.complete(
        cand,
        worker_msgs,
        model,
        stream,
        thinking=thinking,
        search=search,
        **complete_kw,
    ):
        if isinstance(chunk, str):
            state.tc += 1
            state.acc_len += len(chunk)
            if state.ft is None:
                state.ft = time.monotonic()
            if fp:
                fp.feed(chunk)
            yield chunk
        elif isinstance(chunk, dict):
            if "usage" in chunk:
                state.p_usage = chunk["usage"]
            else:
                yield chunk


async def _record_single_result(
    reg: Any, cand: Candidate, state: _SingleExecState
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

    worker_msgs, protocol = prepare_worker_messages(
        msgs, tools, cand, fncall_lang=fncall_lang, protocol_id=protocol_id
    )
    native = cand.native_tools
    fp = (
        FncallStreamParser(tools=tools, protocol=protocol)
        if tools and not native
        else None
    )
    state = _SingleExecState()

    yield {"_meta": {"platform": cand.platform}}

    complete_kw = native_complete_kw(kw, tools, native)

    try:
        async for chunk in _stream_single_chunks(
            adapter,
            cand,
            worker_msgs,
            model,
            stream,
            thinking,
            search,
            complete_kw,
            fp,
            state,
        ):
            yield chunk
        if fp and fp.has_calls:
            _, calls = fp.finalize()
            if calls:
                yield {"tool_calls": calls}
        yield {"usage": _usage_for_response(prompt_len, state.acc_len, state.p_usage)}
        state.ok = True
    except Exception as exc:
        raise maybe_classify_exception(exc)
    finally:
        await _record_single_result(reg, cand, state)


async def record_candidate(reg: Any, info: Dict, ok: bool, prompt_len: int) -> None:
    """记录候选项指标。"""
    try:
        dur = time.monotonic() - info["start"]
        lat = (info["ft"] - info["start"]) if info["ft"] else dur
        gen_dur = (time.monotonic() - info["ft"]) if info["ft"] else dur
        usage = info.get("usage")
        comp_tok = int(usage.get("completion_tokens", 0)) if usage else 0
        await reg.selector.record(
            info["cand"].id,
            ok,
            latency=lat,
            tokens=info["tok"],
            duration=dur,
            generation_dur=gen_dur,
            completion_tokens=comp_tok,
            platform=info["cand"].platform,
        )
        from src.core.dispatch.circuit import get_platform_circuit_breaker

        get_platform_circuit_breaker().record(info["cand"].platform, ok)
    except Exception as e:
        logger.warning("记录候选项 [%s] 指标失败: %s", info["cand"].id, e)


async def run_selected(
    registry: Any,
    sel: List[Candidate],
    final_msgs: List[Dict[str, Any]],
    model: str,
    stream: bool,
    thinking: bool,
    search: bool,
    tools: Optional[List[Dict[str, Any]]],
    fncall_lang: str,
    protocol_id: str,
    extra_kw: Dict[str, Any],
) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
    """对单发或竞速候选项执行请求并产出流式分片。"""
    prompt_len = sum(len(str(m.get("content", ""))) for m in final_msgs)
    if len(sel) == 1:
        async for chunk in single_execute(
            registry,
            sel[0],
            final_msgs,
            model,
            stream,
            thinking,
            search,
            tools,
            prompt_len,
            fncall_lang=fncall_lang,
            protocol_id=protocol_id,
            **extra_kw,
        ):
            yield chunk
        return

    cfg = get_config()
    async for chunk in race_execute(
        registry,
        sel,
        final_msgs,
        model,
        stream,
        thinking,
        search,
        tools,
        prompt_len,
        cfg.gateway.min_tokens,
        fncall_lang=fncall_lang,
        protocol_id=protocol_id,
        **extra_kw,
    ):
        yield chunk
