"""竞速执行 — 多候选项并发请求，选取最快达到 min_tok 的 worker。"""

from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from echotools.fncall.parsers.stream import FncallStreamParser

from src.core.dispatch.cand import Candidate
from src.core.dispatch.engine.support.fncall_context import (
    dump_race_prompt,
    native_complete_kw,
    prepare_worker_messages,
    resolve_protocol,
)
from src.core.utils.errors import NoCandidateError
from src.foundation.logger import get_logger

__all__ = ["race_execute"]

logger = get_logger(__name__)

_RACE_CHUNK_TIMEOUT: float = 120.0
_RACE_WAIT_SLICE: float = 0.25


def _apply_race_event(
    info: Dict[str, Any], tp: str, data: Any, min_tok: int
) -> Optional[Dict[str, Any]]:
    """处理竞速 worker 队列事件，满足 min_tok 时返回 winner info。"""
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
            return info
    elif tp == "done":
        info["done"] = True
    elif tp in ("err", "cancel"):
        info["err"] = True
        if data:
            info["err_msg"] = str(data)
    return None


async def _forward_worker_events(info: Dict[str, Any], merged_queue: "asyncio.Queue") -> None:
    """将单个 worker 队列事件转发到聚合队列。"""
    try:
        while not info["done"] and not info["err"]:
            tp, idx, data = await asyncio.wait_for(
                info["q"].get(), timeout=_RACE_CHUNK_TIMEOUT
            )
            await merged_queue.put((tp, idx, data))
            if tp in ("done", "err", "cancel"):
                break
    except asyncio.TimeoutError:
        await merged_queue.put(("err", info["idx"], "队列消费超时"))
    except asyncio.CancelledError:
        pass
    except Exception as e:
        await merged_queue.put(("err", info["idx"], str(e)))


def _start_forward_tasks(
    infos: List[Dict[str, Any]], merged_queue: "asyncio.Queue"
) -> List["asyncio.Task"]:
    forward_tasks = []
    for info in infos:
        if not info["done"] and not info["err"]:
            task = asyncio.create_task(_forward_worker_events(info, merged_queue))
            forward_tasks.append(task)
    return forward_tasks


def _cancel_forward_tasks(forward_tasks: List["asyncio.Task"]) -> None:
    for task in forward_tasks:
        if not task.done():
            task.cancel()


async def _consume_merged_events(
    infos: List[Dict[str, Any]],
    merged_queue: "asyncio.Queue",
    min_tok: int,
    forward_tasks: List["asyncio.Task"],
) -> Optional[Dict[str, Any]]:
    while True:
        if all(i["done"] or i["err"] for i in infos):
            return None

        try:
            tp, idx, data = await asyncio.wait_for(
                merged_queue.get(), timeout=_RACE_WAIT_SLICE
            )
        except asyncio.TimeoutError:
            continue

        winner = _apply_race_event(infos[idx], tp, data, min_tok)
        if winner is not None:
            _cancel_forward_tasks(forward_tasks)
            return winner


async def _select_race_winner(
    infos: List[Dict[str, Any]], min_tok: int
) -> Optional[Dict[str, Any]]:
    """等待任一 worker 达到 min_tok；使用事件驱动替代轮询。

    优化点：
    1. 使用单个 Queue 聚合所有 worker 事件，避免多次轮询
    2. 减少任务创建和取消开销
    3. 使用 timeout 防止无限等待
    """
    merged_queue: asyncio.Queue = asyncio.Queue()
    forward_tasks = _start_forward_tasks(infos, merged_queue)
    if not forward_tasks:
        return None

    try:
        return await _consume_merged_events(infos, merged_queue, min_tok, forward_tasks)
    finally:
        _cancel_forward_tasks(forward_tasks)


def _cancel_race_workers(infos: List[Dict[str, Any]], *, skip: Optional[Dict] = None) -> None:
    for info in infos:
        if info is skip:
            continue
        info["ev"].set()
        task = info["task"]
        if not task.done():
            task.cancel()


async def _stream_worker_chunks(
    a: Any, c: Candidate, worker_msgs: List[Dict], model: str, stream: bool,
    thinking: bool, search: bool, race_kw: Dict[str, Any],
    idx: int, q: asyncio.Queue, ev: asyncio.Event,
) -> None:
    async for ch in a.complete(
        c, worker_msgs, model, stream,
        thinking=thinking, search=search, **race_kw
    ):
        if ev.is_set():
            break
        await q.put(("chunk", idx, ch))
    await q.put(("done", idx, None))


async def _run_race_worker(
    idx: int,
    c: Candidate,
    q: asyncio.Queue,
    ev: asyncio.Event,
    reg: Any,
    msgs: List[Dict],
    model: str,
    stream: bool,
    thinking: bool,
    search: bool,
    tools: Optional[List[Dict]],
    fncall_lang: str,
    protocol_id: str,
    kw: Dict[str, Any],
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
    race_kw = native_complete_kw(kw, tools, c.native_tools)
    try:
        await _stream_worker_chunks(
            a, c, worker_msgs, model, stream, thinking, search, race_kw, idx, q, ev,
        )
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


def _spawn_race_workers(
    reg: Any,
    cands: List[Candidate],
    msgs: List[Dict],
    model: str,
    stream: bool,
    thinking: bool,
    search: bool,
    tools: Optional[List[Dict]],
    fncall_lang: str,
    protocol_id: str,
    kw: Dict[str, Any],
) -> List[Dict[str, Any]]:
    infos: List[Dict[str, Any]] = []
    for i, c in enumerate(cands):
        q: asyncio.Queue = asyncio.Queue()
        ev = asyncio.Event()
        t = asyncio.ensure_future(
            _run_race_worker(
                i, c, q, ev, reg, msgs, model, stream, thinking, search,
                tools, fncall_lang, protocol_id, kw,
            )
        )
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
    return infos


async def _resolve_winner(
    infos: List[Dict[str, Any]], min_tok: int, reg: Any, prompt_len: int
) -> Dict[str, Any]:
    from src.core.dispatch.engine.execs import record_candidate

    winner = await _select_race_winner(infos, min_tok)
    if winner is not None:
        return winner

    valid = [i for i in infos if not i["err"] and (i["buf"] or i["acc_len"] > 0)]
    if valid:
        return max(valid, key=lambda x: (x["tok"], x["acc_len"]))

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
    raise NoCandidateError("所有并发请求失败: {}".format("; ".join(err_details)))


def _apply_winner_chunk(winner: Dict[str, Any], data: Any, fp: Optional[FncallStreamParser]) -> bool:
    """处理 winner 队列中的单条 chunk 数据，返回是否应跳过 yield。"""
    if isinstance(data, str):
        winner["tok"] += 1
        winner["acc_len"] += len(data)
        if fp:
            fp.feed(data)
        return False
    if isinstance(data, dict) and "usage" in data:
        winner["usage"] = data["usage"]
        return True
    return False


async def _drain_winner_queue(winner: Dict[str, Any], fp: Optional[FncallStreamParser]) -> AsyncGenerator[Union[str, Dict], None]:
    if winner["done"]:
        return
    while True:
        try:
            tp, _, data = await asyncio.wait_for(
                winner["q"].get(), _RACE_CHUNK_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.warning("竞速队列消费超时，提前结束")
            break
        if tp == "chunk":
            if _apply_winner_chunk(winner, data, fp):
                continue
            yield data
        elif tp in ("done", "err", "cancel"):
            break


async def _stream_winner(
    winner: Dict[str, Any], tools: Optional[List[Dict]], prompt_len: int
) -> AsyncGenerator[Union[str, Dict], None]:
    from src.core.dispatch.engine.execs import _usage_for_response

    winner_native = winner["cand"].native_tools
    if tools and not winner_native:
        winner_protocol = resolve_protocol(
            protocol_id="", platform_id=winner["cand"].platform
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

    async for data in _drain_winner_queue(winner, fp):
        yield data

    if fp and fp.has_calls:
        _, calls = fp.finalize()
        if calls:
            yield {"tool_calls": calls}

    yield {"usage": _usage_for_response(prompt_len, winner["acc_len"], winner["usage"])}


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
    from src.core.dispatch.engine.execs import record_candidate

    dump_race_prompt(msgs, tools, cands, fncall_lang=fncall_lang, protocol_id=protocol_id)
    infos = _spawn_race_workers(
        reg, cands, msgs, model, stream, thinking, search, tools, fncall_lang, protocol_id, kw,
    )

    winner: Optional[Dict] = None
    try:
        winner = await _resolve_winner(infos, min_tok, reg, prompt_len)

        _cancel_race_workers(infos, skip=winner)
        for i in infos:
            if i is not winner:
                await record_candidate(reg, i, i["tok"] > 0, prompt_len)

        async for chunk in _stream_winner(winner, tools, prompt_len):
            yield chunk

        await record_candidate(reg, winner, True, prompt_len)

    except NoCandidateError:
        raise
    except Exception:
        _cancel_race_workers(infos)
        raise
