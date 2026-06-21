# -*- coding: utf-8 -*-
from __future__ import annotations

"""OpenAI 兼容路由——Chat Completions 端点

包含流式和非流式聊天补全逻辑：
- _stream_chat: 流式 SSE 聊天补全
- chat_completions: /v1/chat/completions 端点处理函数
"""

import asyncio
import json
import time
import uuid
from typing import Any, Dict, List, Optional

import aiohttp.web

from src.core.config.resolver import resolve_model
from src.core.errors import NoCandidateError, ProviderError
from src.core.server import (
    clean_fncall as _clean_fncall,
)
from src.core.server import (
    get_json as _get_json,
)
from src.core.server import (
    safe_flush as _safe_flush,
)
from src.core.server import REGISTRY_KEY
from src.logger import get_logger
from src.routes.openai_helpers import (
    _cid,
    _err,
    _extract_upload_files,
    _json,
    _normalize_messages,
    _sl,
)

__all__ = [
    "_stream_chat",
    "chat_completions",
]

logger = get_logger(__name__)


# =======================================================================
# Chat Completions
# =======================================================================

async def _stream_chat(
    request: aiohttp.web.Request,
    body: Dict[str, Any],
) -> aiohttp.web.StreamResponse:
    """流式聊天补全。"""
    from src.core import gateway

    cid = _cid()
    ct = int(time.time())
    mdl = resolve_model(body.get("model", ""), "openai")
    messages = _normalize_messages(body.get("messages", []))
    tools_raw = body.get("tools")
    extra = body.get("extra_body") or body.get("extra") or {}
    upload_files = _extract_upload_files(messages)
    proto_override = body.get("protocol", "")

    resp = aiohttp.web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
    await resp.prepare(request)

    ctok = 0
    has_tc = False
    usage_d: Optional[Dict] = None
    buffer = ""
    fncall_buffer = ""
    in_fncall = False
    tool_calls_data: List[Dict[str, Any]] = []
    platform_id: str = ""

    init_chunk_sent = False

    async def _send_init() -> None:
        nonlocal init_chunk_sent
        if init_chunk_sent:
            return
        init_chunk_sent = True
        delta = (
            {"role": "assistant", "content": None}
            if tools_raw
            else {"role": "assistant", "content": ""}
        )
        chunk = {
            "id": cid,
            "object": "chat.completion.chunk",
            "created": ct,
            "model": mdl,
            "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
        }
        await resp.write(
            "data: {}\n\n".format(json.dumps(chunk, ensure_ascii=False)).encode("utf-8")
        )

    async def _send_tc_incremental(tc_list: List[Dict[str, Any]]) -> None:
        """按增量逐步发送 tool_calls 流式块。"""
        chunk_size = 20  # arguments 每次发送的字符数

        for idx, tc in enumerate(tc_list):
            fn = tc.get("function", {})
            name = fn.get("name", "")
            args = fn.get("arguments", "")
            if isinstance(args, dict):
                args = json.dumps(args, ensure_ascii=False)

            # 声明块：id/type/function.name/arguments=""
            decl_chunk = {
                "id": cid,
                "object": "chat.completion.chunk",
                "created": ct,
                "model": mdl,
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": idx,
                                    "id": tc.get(
                                        "id", "call_{}".format(uuid.uuid4().hex[:24])
                                    ),
                                    "type": "function",
                                    "function": {"name": name, "arguments": ""},
                                }
                            ]
                        },
                        "finish_reason": None,
                    }
                ],
            }
            await resp.write(
                "data: {}\n\n".format(
                    json.dumps(decl_chunk, ensure_ascii=False)
                ).encode("utf-8")
            )

            # arguments 增量块
            for start in range(0, max(len(args), 1), chunk_size):
                frag = args[start : start + chunk_size]
                if not frag and start > 0:
                    break
                arg_chunk = {
                    "id": cid,
                    "object": "chat.completion.chunk",
                    "created": ct,
                    "model": mdl,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": idx,
                                        "function": {"arguments": frag},
                                    }
                                ]
                            },
                            "finish_reason": None,
                        }
                    ],
                }
                await resp.write(
                    "data: {}\n\n".format(
                        json.dumps(arg_chunk, ensure_ascii=False)
                    ).encode("utf-8")
                )

    try:
        async for ch in gateway.dispatch(
            registry=request.app[REGISTRY_KEY],
            messages=messages,
            model=mdl,
            stream=True,
            tools=tools_raw,
            thinking=bool(extra.get("thinking")),
            search=bool(extra.get("search")),
            temperature=body.get("temperature"),
            top_p=body.get("top_p"),
            max_tokens=body.get("max_tokens"),
            stop=_sl(body.get("stop")),
            upload_files=upload_files if upload_files else None,
            protocol_id=proto_override,
            tool_choice=body.get("tool_choice"),
            platform=extra.get("platform", ""),
        ):
            if isinstance(ch, str):
                ctok += 1

                if in_fncall:
                    fncall_buffer += ch
                    continue

                buffer += ch

                # Use protocol-aware tag detection.
                # detect_start() 容忍变体（如 `<antml:function_calls >` 或带属性）；
                # 不支持该方法的协议回退到严格 trigger_tags 匹配。
                from src.core.fncall.registry import get_protocol
                proto = get_protocol(protocol_id=proto_override, platform_id=platform_id)
                trigger_tags = proto.get_trigger_tags()

                tag_idx = -1
                detect_start = getattr(proto, "detect_start", None)
                if callable(detect_start):
                    try:
                        found, pos = detect_start(buffer)
                        if found:
                            tag_idx = pos
                    except Exception:
                        pass
                if tag_idx == -1:
                    for tag in trigger_tags:
                        idx = buffer.find(tag)
                        if idx != -1 and (tag_idx == -1 or idx < tag_idx):
                            tag_idx = idx
                if tag_idx != -1:
                    safe_part = buffer[:tag_idx]
                    if safe_part:
                        await _send_init()
                        chunk_data = {
                            "id": cid,
                            "object": "chat.completion.chunk",
                            "created": ct,
                            "model": mdl,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {"content": safe_part},
                                    "finish_reason": None,
                                }
                            ],
                        }
                        await resp.write(
                            "data: {}\n\n".format(
                                json.dumps(chunk_data, ensure_ascii=False)
                            ).encode("utf-8")
                        )
                    fncall_buffer = buffer[tag_idx:]
                    buffer = ""
                    in_fncall = True
                    continue

                safe_part, buffer = _safe_flush(buffer, platform_id=platform_id, protocol_id=proto_override)
                if safe_part:
                    _log_chunks = request.get("_req_log_chunks")
                    if _log_chunks is not None:
                        _log_chunks.append(safe_part)
                    _log_id = request.get("_req_log_id")
                    if _log_id:
                        try:
                            from src.webui.services.request_log import request_broker
                            request_broker.push_event({"type": "request_chunk", "id": _log_id, "delta": safe_part})
                        except Exception:
                            pass
                    await _send_init()
                    chunk_data = {
                        "id": cid,
                        "object": "chat.completion.chunk",
                        "created": ct,
                        "model": mdl,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": safe_part},
                                "finish_reason": None,
                            }
                        ],
                    }
                    await resp.write(
                        "data: {}\n\n".format(
                            json.dumps(chunk_data, ensure_ascii=False)
                        ).encode("utf-8")
                    )

            elif isinstance(ch, dict):
                if "_meta" in ch:
                    platform_id = ch["_meta"].get("platform", "")
                    if platform_id:
                        resp._platform = platform_id
                elif "thinking" in ch:
                    await _send_init()
                    chunk_data = {
                        "id": cid,
                        "object": "chat.completion.chunk",
                        "created": ct,
                        "model": mdl,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"reasoning_content": ch["thinking"]},
                                "finish_reason": None,
                            }
                        ],
                    }
                    await resp.write(
                        "data: {}\n\n".format(
                            json.dumps(chunk_data, ensure_ascii=False)
                        ).encode("utf-8")
                    )
                elif "tool_calls" in ch:
                    tool_calls_data = ch["tool_calls"]
                    has_tc = True
                elif "usage" in ch:
                    usage_d = ch["usage"]
    except asyncio.CancelledError:
        return resp
    except ConnectionResetError:
        return resp
    except Exception as e:
        logger.error("流式错误: %s", e, exc_info=True)
        err_data = json.dumps(
            {"error": {"message": str(e), "type": "server_error"}},
            ensure_ascii=False,
        )
        try:
            await resp.write("data: {}\n\n".format(err_data).encode("utf-8"))
        except Exception as exc:
            logger.debug("流式错误信息写回失败，可能连接已关闭: %s", exc)
        return resp

    if buffer and not in_fncall:
        await _send_init()
        chunk_data = {
            "id": cid,
            "object": "chat.completion.chunk",
            "created": ct,
            "model": mdl,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": buffer},
                    "finish_reason": None,
                }
            ],
        }
        await resp.write(
            "data: {}\n\n".format(json.dumps(chunk_data, ensure_ascii=False)).encode(
                "utf-8"
            )
        )

    if in_fncall and fncall_buffer and not tool_calls_data:
        from src.core.fncall.registry import get_protocol
        proto = get_protocol(protocol_id=proto_override, platform_id=platform_id)
        _, tool_calls_data = proto.parse(fncall_buffer, tools_raw)
        if tool_calls_data:
            has_tc = True

    if tool_calls_data:
        await _send_init()
        await _send_tc_incremental(tool_calls_data)
    else:
        # 确保 init_chunk 至少发送过一次（纯文本流空响应情况）
        await _send_init()

    fr = "tool_calls" if has_tc else "stop"
    u = usage_d or {
        "prompt_tokens": 0,
        "completion_tokens": ctok,
        "total_tokens": ctok,
    }

    # finish_reason 块（不含 usage）
    final_chunk = {
        "id": cid,
        "object": "chat.completion.chunk",
        "created": ct,
        "model": mdl,
        "choices": [{"index": 0, "delta": {}, "finish_reason": fr}],
    }
    # usage 独立块（choices 为空列表）
    usage_chunk = {
        "id": cid,
        "object": "chat.completion.chunk",
        "created": ct,
        "model": mdl,
        "choices": [],
        "usage": u,
    }
    try:
        await resp.write(
            "data: {}\n\n".format(json.dumps(final_chunk, ensure_ascii=False)).encode(
                "utf-8"
            )
        )
        await resp.write(
            "data: {}\n\n".format(json.dumps(usage_chunk, ensure_ascii=False)).encode(
                "utf-8"
            )
        )
        await resp.write(b"data: [DONE]\n\n")
    except Exception as exc:
        logger.debug("流式结束块写回失败，可能连接已关闭: %s", exc)
    return resp


async def chat_completions(
    request: aiohttp.web.Request,
) -> aiohttp.web.StreamResponse:
    """聊天补全端点 /v1/chat/completions。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    from src.core import gateway

    if request.method != "POST":
        return _err(
            405,
            "Method {} not allowed. Use POST for /v1/chat/completions.".format(
                request.method
            ),
            "method_not_allowed",
        )

    body = await _get_json(request)
    if body is None:
        return _err(400, "Invalid JSON in request body", "invalid_json")

    if "messages" in body and isinstance(body["messages"], list):
        body["messages"] = _normalize_messages(body["messages"])

    messages = body.get("messages", [])
    if not messages:
        return _err(400, "messages is required", "missing_field", param="messages")

    mdl = body.get("model", "")
    mdl = resolve_model(mdl, "openai")
    stream = bool(body.get("stream", False))

    if stream:
        return await _stream_chat(request, body)

    cid = _cid()
    ct = int(time.time())
    extra = body.get("extra_body") or body.get("extra") or {}
    cp: List[str] = []
    tp: List[str] = []
    tcs: List[Dict] = []
    usage_d: Optional[Dict] = None
    upload_files = _extract_upload_files(messages)
    platform_id: str = ""
    proto_override = body.get("protocol", "")

    try:
        async for ch in gateway.dispatch(
            registry=request.app[REGISTRY_KEY],
            messages=_normalize_messages(messages),
            model=mdl,
            stream=False,
            tools=body.get("tools"),
            thinking=bool(extra.get("thinking")),
            search=bool(extra.get("search")),
            temperature=body.get("temperature"),
            top_p=body.get("top_p"),
            max_tokens=body.get("max_tokens"),
            stop=_sl(body.get("stop")),
            upload_files=upload_files if upload_files else None,
            protocol_id=proto_override,
            tool_choice=body.get("tool_choice"),
            platform=extra.get("platform", ""),
        ):
            if isinstance(ch, str):
                cp.append(ch)
            elif isinstance(ch, dict):
                if "_meta" in ch:
                    platform_id = ch["_meta"].get("platform", "")
                elif "thinking" in ch:
                    tp.append(ch["thinking"])
                elif "tool_calls" in ch:
                    tcs = ch["tool_calls"]
                elif "usage" in ch:
                    usage_d = ch["usage"]
    except NoCandidateError as e:
        return _err(503, str(e), "no_candidate", "service_unavailable")
    except ProviderError as e:
        return _err(502, str(e), "provider_error", "upstream_error")
    except Exception as e:
        logger.error("补全异常: %s", e, exc_info=True)
        return _err(500, str(e), "internal_error", "server_error")

    content = "".join(cp)

    # 兜底：若网关未产出 tool_calls 块（请求未带 tools，或流式解析器
    # 漏掉变体标签），对完整内容再跑一次协议解析，把 antml / bracket /
    # 其它协议的 tool_calls 抠出来。
    if not tcs and content:
        try:
            from src.core.fncall.registry import get_protocol
            proto = get_protocol(platform_id=platform_id)
            cleaned, extracted = proto.parse(content, body.get("tools"))
            if extracted:
                tcs = extracted
                content = cleaned
        except Exception as exc:
            logger.debug("非流式兜底 fncall 解析失败: %s", exc)

    content = _clean_fncall(content, platform_id=platform_id, protocol_id=proto_override)

    u = usage_d or {
        "prompt_tokens": 0,
        "completion_tokens": len(content) // 3 if content else 0,
        "total_tokens": len(content) // 3 if content else 0,
    }
    msg: Dict[str, Any] = {"role": "assistant"}
    if content:
        msg["content"] = content
    if tp:
        msg["reasoning_content"] = "".join(tp)
    if tcs:
        msg["tool_calls"] = tcs

    return _json(
        {
            "id": cid,
            "object": "chat.completion",
            "created": ct,
            "model": mdl,
            "choices": [
                {
                    "index": 0,
                    "message": msg,
                    "finish_reason": "tool_calls" if tcs else "stop",
                }
            ],
            "usage": u,
        }
    )
