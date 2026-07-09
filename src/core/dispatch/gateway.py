from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from src.core.dispatch.candidate import Candidate
from src.core.config import get_config
from src.core.errors import NoCandidateError, ProviderError
from src.core.fncall.registry import get_protocol
from echotools.fncall.parsers.stream import FncallStreamParser
from src.core.fncall.prompt.inject import inject_fncall
from echotools.dispatch.usage import fallback_usage as _fallback_usage
from echotools.dispatch.usage import normalize_usage as _normalize_usage
from echotools.logger.manager import get_logger

__all__ = ["dispatch"]
logger = get_logger(__name__)

# 竞速队列消费最大等待秒数
_RACE_CHUNK_TIMEOUT: float = 120.0




async def _wait_for_candidates(
    registry: Any, model: str, timeout: float = 15.0, platform: str = ""
) -> List[Candidate]:
    """等待候选项就绪。

    Args:
        registry: 注册表实例。
        model: 模型名。
        timeout: 最大等待秒数。
        platform: 平台名，非空时过滤候选项。

    Returns:
        可用候选项列表。
    """
    deadline = time.monotonic() + timeout
    cfg = get_config()
    while time.monotonic() < deadline:
        cands = await registry.get_candidates(model)
        if platform:
            cands = [c for c in cands if c.platform == platform]
        if cands:
            return cands
        await registry.ensure_candidates(
            model, max(cfg.gateway.concurrent_count, 3)
        )
        await asyncio.sleep(0.5)
    return []


def _fold_system_into_user(
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


def _build_dispatch_extra_kw(
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


async def _select_dispatch_candidates(
    registry: Any,
    cands: List[Candidate],
    stream: bool,
) -> tuple[int, List[Candidate]]:
    """根据网关配置选择并发数与候选项子集。"""
    cfg = get_config()
    gw = cfg.gateway
    racing_pool = (
        [c for c in cands if gw.is_platform_enabled(c.platform)]
        if gw.group_list_set
        else cands
    )
    n = 1
    if gw.concurrent_enabled and stream and len(racing_pool) > 1 and len(cands) > 1:
        n = min(gw.concurrent_count, len(racing_pool))
    sel_pool = racing_pool if n > 1 else cands
    sel = await registry.selector.select(sel_pool, n)
    if not sel:
        raise NoCandidateError("TAS 选择失败")
    return n, sel


async def _run_selected(
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
        async for chunk in _single(
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
    async for chunk in _race(
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


def _fncall_lang(kw: Dict[str, Any]) -> str:
    raw = kw.get("fncall_lang", "en")
    return raw if raw in ("en", "zh") else "en"


async def dispatch(
    registry: Any,
    messages: List[Dict],
    model: str,
    stream: bool,
    *,
    tools: Optional[List[Dict]] = None,
    thinking: bool = False,
    search: bool = False,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    max_tokens: Optional[int] = None,
    stop: Optional[List[str]] = None,
    upload_files: Optional[List[Any]] = None,
    platform: str = "",
    **kw: Any,
) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
    """核心分发：选择候选项并执行单发或竞速请求。"""
    final_msgs = _fold_system_into_user(messages, tools)

    cands = await _wait_for_candidates(registry, model, timeout=15.0, platform=platform)
    if not cands:
        raise NoCandidateError("无候选项: {}".format(model))

    n, sel = await _select_dispatch_candidates(registry, cands, stream)

    extra_kw = _build_dispatch_extra_kw(
        kw,
        upload_files=upload_files,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        stop=stop,
    )

    async for chunk in _run_selected(
        registry,
        sel,
        final_msgs,
        model,
        stream,
        thinking,
        search,
        tools,
        _fncall_lang(kw),
        kw.get("protocol_id", ""),
        extra_kw,
    ):
        yield chunk


async def _single(
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
    """单候选项执行。

    Args:
        reg: 注册表。
        cand: 候选项。
        msgs: 消息列表。
        model: 模型名。
        stream: 是否流式。
        thinking: thinking 模式。
        search: 搜索模式。
        tools: 工具列表。
        prompt_len: 提示文本长度。
        **kw: 额外参数。

    Yields:
        str 或 dict。
    """
    adapter = reg.adapter_for(cand)
    if not adapter:
        raise ProviderError("无适配器: {}".format(cand.platform))

    # 按平台解析协议并注入工具定义（native_tools 平台直接透传 tools）
    protocol = None
    native = getattr(cand, 'native_tools', False)
    if tools:
        if native:
            worker_msgs = msgs
        else:
            if protocol_id:
                protocol = get_protocol(protocol_id=protocol_id)
            else:
                protocol = get_protocol(platform_id=cand.platform)
            worker_msgs = inject_fncall(msgs, tools, protocol, lang=fncall_lang)
    else:
        worker_msgs = msgs

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
    acc_parts: List[str] = []

    # Yield platform info so route can use correct protocol for cleaning
    yield {"_meta": {"platform": cand.platform}}

    complete_kw: Dict[str, Any] = dict(kw)
    if native and tools:
        complete_kw["tools"] = tools
        _tc = kw.get("tool_choice")
        if _tc is not None:
            complete_kw["tool_choice"] = _tc

    try:
        async for chunk in adapter.complete(
            cand, worker_msgs, model, stream, thinking=thinking, search=search, **complete_kw
        ):
            if isinstance(chunk, str):
                tc += 1
                acc_parts.append(chunk)
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
        acc = "".join(acc_parts)
        usage = (
            _normalize_usage(p_usage, prompt_len, acc)
            if p_usage
            else _fallback_usage(prompt_len, acc)
        )
        yield {"usage": usage}
        ok = True
    except Exception:
        raise
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


async def _race(
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
    """多候选项竞速执行。

    Args:
        reg: 注册表。
        cands: 候选项列表。
        msgs: 消息列表。
        model: 模型名。
        stream: 是否流式。
        thinking: thinking 模式。
        search: 搜索模式。
        tools: 工具列表。
        prompt_len: 提示文本长度。
        min_tok: 竞速最小 token 数。
        **kw: 额外参数。

    Yields:
        str 或 dict。
    """
    infos: List[Dict[str, Any]] = []

    async def _w(
        idx: int, c: Candidate, q: asyncio.Queue, ev: asyncio.Event
    ) -> None:
        """单个候选项 worker。

        Args:
            idx: 序号。
            c: 候选项。
            q: 输出队列。
            ev: 停止事件。
        """
        a = reg.adapter_for(c)
        if not a:
            try:
                await q.put(("err", idx, "无适配器: {}".format(c.platform)))
            except Exception as e:
                logger.debug("竞速 worker[%d] 发送错误消息失败: %s", idx, e)
            return
        # 按平台解析协议并注入工具定义（native_tools 平台直接透传 tools）
        worker_msgs = msgs
        _native = getattr(c, 'native_tools', False)
        if tools:
            if _native:
                worker_msgs = msgs
            else:
                if protocol_id:
                    protocol = get_protocol(protocol_id=protocol_id)
                else:
                    protocol = get_protocol(platform_id=c.platform)
                worker_msgs = inject_fncall(
                    msgs, tools, protocol, lang=fncall_lang, dump_prompt=False
                )
        _race_kw = dict(kw)
        if _native and tools:
            _race_kw["tools"] = tools
            _tc = kw.get("tool_choice")
            if _tc is not None:
                _race_kw["tool_choice"] = _tc
        try:
            async for ch in a.complete(
                c, worker_msgs, model, stream,
                thinking=thinking, search=search, **_race_kw
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

    # 并发竞速：worker 启动前统一转储一次 prompt，避免 N 个 worker 各写一份
    # native_tools 平台无需协议转储
    _any_native = any(getattr(c, 'native_tools', False) for c in cands)
    if tools and cands and not _any_native:
        _dump_protocol = (
            get_protocol(protocol_id=protocol_id)
            if protocol_id
            else get_protocol(platform_id=cands[0].platform)
        )
        inject_fncall(msgs, tools, _dump_protocol, lang=fncall_lang, dump_prompt=True)

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
                "acc_parts": [],
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
                        info["acc_parts"].append(data)
                        if info["ft"] is None:
                            info["ft"] = time.monotonic()
                    elif isinstance(data, dict):
                        if "usage" in data:
                            info["usage"] = data["usage"]
                        elif data.get("thinking"):
                            info["acc_parts"].append(str(data["thinking"]))
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
                if not i["err"] and (i["buf"] or i["acc_parts"])
            ]
            if valid:
                winner = max(
                    valid,
                    key=lambda x: (x["tok"], len("".join(x["acc_parts"]))),
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
                for i in infos:
                    await _rec(reg, i, False, prompt_len)
                raise NoCandidateError(
                    "所有并发请求失败: {}".format("; ".join(err_details))
                )

        # 停止其他 workers
        for i in infos:
            if i is not winner:
                i["ev"].set()
                if not i["task"].done():
                    i["task"].cancel()
                await _rec(reg, i, i["tok"] > 0, prompt_len)

        # 获取 winner 的平台协议（native_tools 平台无需协议和流式解析器）
        _winner_native = getattr(winner["cand"], 'native_tools', False)
        if tools and not _winner_native:
            winner_protocol = (
                get_protocol(protocol_id=protocol_id)
                if protocol_id
                else get_protocol(platform_id=winner["cand"].platform)
            )
        else:
            winner_protocol = None
        fp = (
            FncallStreamParser(tools=tools, protocol=winner_protocol)
            if tools and not _winner_native
            else None
        )

        # Yield platform info so route can use correct protocol for cleaning
        yield {"_meta": {"platform": winner["cand"].platform}}

        # 输出缓冲区
        for ch in winner["buf"]:
            if isinstance(ch, str) and fp:
                fp.feed(ch)
            if isinstance(ch, dict) and "usage" in ch:
                winner["usage"] = ch["usage"]
                continue
            yield ch

        # 继续消费队列
        if not winner["done"]:
            while True:
                try:
                    tp, _, data = await asyncio.wait_for(
                        winner["q"].get(), _RACE_CHUNK_TIMEOUT
                    )
                    if tp == "chunk":
                        if isinstance(data, str):
                            winner["tok"] += 1
                            winner["acc_parts"].append(data)
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

        acc = "".join(winner["acc_parts"])
        usage = (
            _normalize_usage(winner["usage"], prompt_len, acc)
            if winner["usage"]
            else _fallback_usage(prompt_len, acc)
        )
        yield {"usage": usage}
        await _rec(reg, winner, True, prompt_len)

    except NoCandidateError:
        raise
    except Exception:
        for i in infos:
            i["ev"].set()
            if not i["task"].done():
                i["task"].cancel()
        raise


async def _rec(
    reg: Any, info: Dict, ok: bool, prompt_len: int
) -> None:
    """记录候选项指标。

    Args:
        reg: 注册表。
        info: worker 信息字典。
        ok: 是否成功。
        prompt_len: 提示文本长度（保留接口）。
    """
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
