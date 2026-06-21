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
    """核心分发——选择候选项并执行请求。

    Args:
        registry: 平台注册表。
        messages: 消息列表。
        model: 模型名。
        stream: 是否流式。
        tools: 工具列表（可选）。
        thinking: 是否启用 thinking 模式。
        search: 是否启用搜索。
        temperature: 温度参数。
        top_p: top_p 参数。
        max_tokens: 最大 token 数。
        stop: 停止序列。
        upload_files: 待上传文件列表 [(file_data, filename), ...]。
        platform: 平台名，非空时过滤候选项。
        **kw: 额外参数透传。

    Yields:
        str 或 dict（按 yield 协议）。
    """
    cfg = get_config()

    raw_fncall_lang = kw.get("fncall_lang", "en")
    fncall_lang = raw_fncall_lang if raw_fncall_lang in ("en", "zh") else "en"

    # 协议注入延迟到候选项选择后（_single/_race 中按平台解析协议）
    final_msgs = messages

    # 无 tools 时，将 system 消息折叠到第一条 user 消息中，
    # 确保所有平台都能收到系统指令（部分平台不原生支持 system role）
    if not tools:
        sys_parts = []
        non_sys = []
        for m in final_msgs:
            if m.get("role") == "system":
                c = m.get("content", "")
                if c:
                    sys_parts.append(c if isinstance(c, str) else str(c))
            else:
                non_sys.append(m)
        if sys_parts:
            sys_text = "\n\n".join(sys_parts)
            merged = list(non_sys)
            for i, m in enumerate(merged):
                if m.get("role") == "user":
                    old = m.get("content", "")
                    old_text = old if isinstance(old, str) else str(old)
                    merged[i] = {**m, "content": sys_text + "\n\n" + old_text}
                    break
            else:
                merged.insert(0, {"role": "user", "content": sys_text})
            final_msgs = merged

    if tools:
        thinking = False

    cands = await _wait_for_candidates(registry, model, timeout=15.0, platform=platform)
    if not cands:
        raise NoCandidateError("无候选项: {}".format(model))

    # [gateway].group_list 决定"谁允许并发竞速"，不决定"谁能路由"：
    # - 所有候选始终进入路由池
    # - 只有当竞速池（racing-eligible）≥ 2 时才启用并发；否则单发
    # - 因此非名单内平台仍可服务请求，只是该请求强制 n=1
    gw = cfg.gateway
    racing_pool = (
        [c for c in cands if gw.is_platform_enabled(c.platform)]
        if gw.group_list_set
        else cands
    )

    n = 1
    if (
        gw.concurrent_enabled
        and len(racing_pool) > 1
        and len(cands) > 1
    ):
        n = min(gw.concurrent_count, len(racing_pool))
    sel_pool = racing_pool if n > 1 else cands
    sel = await registry.selector.select(sel_pool, n)
    if not sel:
        raise NoCandidateError("TAS 选择失败")

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

    prompt_len = sum(len(str(m.get("content", ""))) for m in final_msgs)
##    print(final_msgs[0]["content"])
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
            protocol_id=kw.get("protocol_id", ""),
            **extra_kw,
        ):
##            print(chunk)
            yield chunk
        return

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
        protocol_id=kw.get("protocol_id", ""),
        **extra_kw,
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
                    elif isinstance(data, dict) and "usage" in data:
                        info["usage"] = data["usage"]
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
                i for i in infos if i["buf"] and not i["err"]
            ]
            if valid:
                winner = max(valid, key=lambda x: x["tok"])
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
