from __future__ import annotations

import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from echotools.dispatch.usage import fallback_usage as _fallback_usage
from echotools.dispatch.usage import normalize_usage as _normalize_usage

from src.core.dispatch.cand import Candidate
from src.core.dispatch.engine.race_worker import race_execute
from src.core.dispatch.engine.support.single_exec import single_execute
from src.foundation.config import get_config
from src.foundation.logger import get_logger

__all__ = ["single_execute", "race_execute", "record_candidate", "run_selected", "_usage_for_response"]

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
