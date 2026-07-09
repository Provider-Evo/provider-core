from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from echotools.fncall.parsers.stream import FncallStreamParser
from echotools.dispatch.usage import fallback_usage as _fallback_usage
from echotools.dispatch.usage import normalize_usage as _normalize_usage

from src.core.config import get_config
from src.core.dispatch.candidate import Candidate
from src.core.dispatch.engine.fncall_context import (
    dump_race_prompt,
    native_complete_kw,
    prepare_worker_messages,
    resolve_protocol,
)
from src.core.errors import NoCandidateError, ProviderError
from src.core.errors.http_errors import maybe_classify_exception
from src.foundation.logger import get_logger

logger = get_logger(__name__)

# 竞速队列消费最大等待秒数
_RACE_CHUNK_TIMEOUT: float = 120.0


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


def _cancel_race_workers(infos: List[Dict[str, Any]], *, skip: Optional[Dict] = None) -> None:
    for info in infos:
        if info is skip:
            continue
        info["ev"].set()
        task = info["task"]
        if not task.done():
            task.cancel()


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
    native = getattr(cand, "native_tools", False)
    fp = (
        FncallStreamParser(tools=tools, protocol=protocol)
        if tools and not native
        else None
    )
    start = time.monotonic()
    ft: Optional[float] = None
    tc = 0
    ok = False
    p_usage: Optional[Dict] = None
    acc_len = 0

    yield {"_meta": {"platform": cand.platform}}

    complete_kw = native_complete_kw(kw, tools, native)

    try:
        async for chunk in adapter.complete(
            cand, worker_msgs, model, stream, thinking=thinking, search=search, **complete_kw
        ):
            if isinstance(chunk, str):
                tc += 1
                acc_len += len(chunk)
                if ft is None:
                    ft = time.monotonic()
                if fp:
                    fp.feed(chunk)
                yield chunk
            elif isinstance(chunk, dict):
                if "usage" in chunk:
                    p_usage = chunk["usage"]
                else:
                    yield chunk
        if fp and fp.has_calls:
            _, calls = fp.finalize()
            if calls:
                yield {"tool_calls": calls}
        yield {"usage": _usage_for_response(prompt_len, acc_len, p_usage)}
        ok = True
    except Exception as exc:
        raise maybe_classify_exception(exc)
    finally:
        dur = time.monotonic() - start
        lat = (ft - start) if ft else dur
        gen_dur = (time.monotonic() - ft) if ft else dur
        comp_tok = (
            int(p_usage.get("completion_tokens", 0)) if p_usage else 0
        )
        await reg.selector.record(
            cand.id, ok, latency=lat, tokens=tc, duration=dur,
            generation_dur=gen_dur, completion_tokens=comp_tok,
            platform=cand.platform,
        )


async def race_execute(
    reg: Any,
    cands: List[Candidate],
    msgs: List[Dict],
    model: str,
    stream: bool,
    thinking: bool,
    search: bool,
    tools: Optional[List[Dict]],
    prompt_len: int,
    min_tok: int,
    fncall_lang: str = "en",
    protocol_id: str = "",
    **kw: Any,
) -> AsyncGenerator[Union[str, Dict], None]:
    """多候选项竞速执行。"""
    infos: List[Dict[str, Any]] = []

    async def _w(
        idx: int, c: Candidate, q: asyncio.Queue, ev: asyncio.Event
    ) -> None:
        a = reg.adapter_for(c)
        if not a:
            try:
                await q.put(("err", idx, "无适配器: {}".format(c.platform)))
            except Exception as e:
                logger.debug("竞速 worker[%d] 发送错误消息失败: %s", idx, e)
            return
        worker_msgs, _ = prepare_worker_messages(
            msgs,
            tools,
            c,
            fncall_lang=fncall_lang,
            protocol_id=protocol_id,
            dump_prompt=False,
        )
        native = getattr(c, "native_tools", False)
        race_kw = native_complete_kw(kw, tools, native)
        try:
            async for ch in a.complete(
                c, worker_msgs, model, stream,
                thinking=thinking, search=search, **race_kw
            ):
                if ev.is_set():
                    break
                await q.put(("chunk", idx, ch))
            await q.put(("done", idx, None))
        except asyncio.CancelledError:
            try:
                await q.put(("cancel", idx, None))
            except Exception as e:
                logger.debug("竞速 worker[%d] 发送取消消息失败: %s", idx, e)
        except Exception as e:
            try:
                await q.put(("err", idx, str(e)))
            except Exception as e2:
                logger.debug("竞速 worker[%d] 发送错误消息失败: %s", idx, e2)

    dump_race_prompt(msgs, tools, cands, fncall_lang=fncall_lang, protocol_id=protocol_id)

    for i, c in enumerate(cands):
        q: asyncio.Queue = asyncio.Queue()
        ev = asyncio.Event()
        t = asyncio.ensure_future(_w(i, c, q, ev))
        infos.append(
            {
                "idx": i,
                "cand": c,
                "q": q,
                "ev": ev,
                "task": t,
                "tok": 0,
                "buf": [],
                "start": time.monotonic(),
                "ft": None,
                "done": False,
                "err": False,
                "err_msg": "",
                "acc_len": 0,
                "usage": None,
            }
        )

    winner: Optional[Dict] = None
    try:
        while winner is None:
            if all(i["done"] or i["err"] for i in infos):
                break
            for info in infos:
                if info["done"] or info["err"]:
                    continue
                try:
                    tp, _, data = info["q"].get_nowait()
                except asyncio.QueueEmpty:
                    continue
                if tp == "chunk":
                    info["buf"].append(data)
                    if isinstance(data, str):
                        info["tok"] += 1
                        info["acc_len"] += len(data)
                        if info["ft"] is None:
                            info["ft"] = time.monotonic()
                    elif isinstance(data, dict):
                        if "usage" in data:
                            info["usage"] = data["usage"]
                        elif data.get("thinking"):
                            info["acc_len"] += len(str(data["thinking"]))
                    if info["tok"] >= min_tok:
                        winner = info
                        break
                elif tp == "done":
                    info["done"] = True
                elif tp in ("err", "cancel"):
                    info["err"] = True
                    if data:
                        info["err_msg"] = str(data)
            if winner is None:
                await asyncio.sleep(0.02)

        if winner is None:
            valid = [
                i
                for i in infos
                if not i["err"] and (i["buf"] or i["acc_len"] > 0)
            ]
            if valid:
                winner = max(
                    valid,
                    key=lambda x: (x["tok"], x["acc_len"]),
                )
            else:
                err_details = []
                for i in infos:
                    c = i["cand"]
                    em = i.get("err_msg", "")
                    err_details.append(
                        "[{}][{}] {}".format(i["idx"], c.resource_id, em) if em
                        else "[{}] {}".format(i["idx"], c.resource_id)
                    )
                _cancel_race_workers(infos)
                for i in infos:
                    await record_candidate(reg, i, False, prompt_len)
                raise NoCandidateError(
                    "所有并发请求失败: {}".format("; ".join(err_details))
                )

        _cancel_race_workers(infos, skip=winner)
        for i in infos:
            if i is not winner:
                await record_candidate(reg, i, i["tok"] > 0, prompt_len)

        winner_native = getattr(winner["cand"], "native_tools", False)
        if tools and not winner_native:
            winner_protocol = resolve_protocol(
                protocol_id=protocol_id, platform_id=winner["cand"].platform
            )
        else:
            winner_protocol = None
        fp = (
            FncallStreamParser(tools=tools, protocol=winner_protocol)
            if tools and not winner_native
            else None
        )

        yield {"_meta": {"platform": winner["cand"].platform}}

        for ch in winner["buf"]:
            if isinstance(ch, str) and fp:
                fp.feed(ch)
            if isinstance(ch, dict) and "usage" in ch:
                winner["usage"] = ch["usage"]
                continue
            yield ch

        if not winner["done"]:
            while True:
                try:
                    tp, _, data = await asyncio.wait_for(
                        winner["q"].get(), _RACE_CHUNK_TIMEOUT
                    )
                    if tp == "chunk":
                        if isinstance(data, str):
                            winner["tok"] += 1
                            winner["acc_len"] += len(data)
                            if fp:
                                fp.feed(data)
                        elif isinstance(data, dict) and "usage" in data:
                            winner["usage"] = data["usage"]
                            continue
                        yield data
                    elif tp in ("done", "err", "cancel"):
                        break
                except asyncio.TimeoutError:
                    logger.warning("竞速队列消费超时，提前结束")
                    break

        if fp and fp.has_calls:
            _, calls = fp.finalize()
            if calls:
                yield {"tool_calls": calls}

        yield {
            "usage": _usage_for_response(
                prompt_len, winner["acc_len"], winner["usage"]
            )
        }
        await record_candidate(reg, winner, True, prompt_len)

    except NoCandidateError:
        raise
    except Exception:
        _cancel_race_workers(infos)
        raise


async def record_candidate(
    reg: Any, info: Dict, ok: bool, prompt_len: int
) -> None:
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
