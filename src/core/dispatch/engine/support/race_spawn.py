"""竞速 worker 创建与分片转发。"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional

from src.core.dispatch.cand import Candidate
from src.core.dispatch.engine.support.fncall_context import (
    native_complete_kw,
    prepare_worker_messages,
)
from src.foundation.logger import get_logger

logger = get_logger(__name__)


async def _stream_worker_chunks(
    a: Any,
    c: Candidate,
    worker_msgs: List[Dict],
    model: str,
    stream: bool,
    thinking: bool,
    search: bool,
    race_kw: Dict[str, Any],
    idx: int,
    q: asyncio.Queue,
    ev: asyncio.Event,
) -> None:
    async for ch in a.complete(
        c, worker_msgs, model, stream, thinking=thinking, search=search, **race_kw
    ):
        if ev.is_set():
            break
        await q.put(("chunk", idx, ch))
    await q.put(("done", idx, None))


async def _put_worker_queue_msg(q: asyncio.Queue, tp: str, idx: int, data: Any) -> None:
    try:
        await q.put((tp, idx, data))
    except Exception as exc:
        logger.debug("竞速 worker[%d] 发送 %s 消息失败: %s", idx, tp, exc)


async def _race_worker_stream(
    a: Any,
    c: Candidate,
    worker_msgs: List[Dict],
    model: str,
    stream: bool,
    thinking: bool,
    search: bool,
    race_kw: Dict[str, Any],
    idx: int,
    q: asyncio.Queue,
    ev: asyncio.Event,
) -> None:
    try:
        await _stream_worker_chunks(
            a, c, worker_msgs, model, stream, thinking, search, race_kw, idx, q, ev
        )
    except asyncio.CancelledError:
        await _put_worker_queue_msg(q, "cancel", idx, None)
    except Exception as exc:
        await _put_worker_queue_msg(q, "err", idx, str(exc))


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
        await _put_worker_queue_msg(q, "err", idx, "无适配器: {}".format(c.platform))
        return
    worker_msgs, _ = prepare_worker_messages(
        msgs,
        tools,
        c,
        fncall_lang=fncall_lang,
        protocol_id=protocol_id,
        dump_prompt=False,
        thinking=thinking,
        thinking_mode=kw.get("thinking_mode"),
        max_thinking_length=kw.get("max_thinking_length"),
    )
    race_kw = native_complete_kw(kw, tools, c.native_tools)
    await _race_worker_stream(
        a, c, worker_msgs, model, stream, thinking, search, race_kw, idx, q, ev
    )


def _new_race_worker_info(
    i: int, c: Candidate, q: asyncio.Queue, ev: asyncio.Event, task: Any
) -> Dict[str, Any]:
    return {
        "idx": i,
        "cand": c,
        "q": q,
        "ev": ev,
        "task": task,
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


def spawn_race_workers(
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
        task = asyncio.ensure_future(
            _run_race_worker(
                i, c, q, ev, reg, msgs, model, stream, thinking, search,
                tools, fncall_lang, protocol_id, kw,
            )
        )
        infos.append(_new_race_worker_info(i, c, q, ev, task))
    return infos
