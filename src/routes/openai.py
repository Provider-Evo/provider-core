# -*- coding: utf-8 -*-
from __future__ import annotations

"""OpenAI 兼容路由——aiohttp.web 实现"""

import asyncio
import binascii
import json
import time
import uuid
from typing import Any, Dict, List, Optional, Union

import aiohttp.web

from src.core.config.resolver import resolve_model
from src.core.errors import NoCandidateError, NotSupportedError, ProviderError
from src.core.http import (
    clean_fncall as _clean_fncall,
)
from src.core.http import (
    get_json as _get_json,
)
from src.core.http import (
    safe_flush as _safe_flush,
)
from src.core.server import REGISTRY_KEY, SESSION_KEY, json_response
from src.core.tools import normalize_content, parse_fncall_xml
from src.logger import get_logger

__all__ = ["setup_routes"]
logger = get_logger(__name__)

# fncall 标签
_FNCALL_START = "<function="
_FNCALL_END = "</" + "function>"
_FNCALL_OPEN_TAG = "<function_calls>"
_FNCALL_CLOSE_TAG = "</function_calls>"

# ═══════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════════════


def _id(prefix: str) -> str:
    return "{}-{}".format(prefix, uuid.uuid4().hex[:24])


def _cid() -> str:
    return _id("chatcmpl")


def _bid() -> str:
    return _id("batch")


def _fid() -> str:
    return _id("file")


def _aid() -> str:
    return _id("asst")


def _tid() -> str:
    return _id("thread")


def _rid() -> str:
    return _id("run")


def _vid() -> str:
    return _id("vs")


def _uid() -> str:
    return _id("upload")


def _json(data: Any, status: int = 200) -> aiohttp.web.Response:
    return json_response(data, status=status)


def _err(
    status: int,
    message: str,
    code: str = "error",
    typ: str = "invalid_request_error",
    param: Optional[str] = None,
) -> aiohttp.web.Response:
    """构建错误 JSON 响应。

    Args:
        status: HTTP 状态码。
        message: 错误信息。
        code: 错误代码。
        typ: 错误类型。
        param: 相关参数名。

    Returns:
        Response 实例。
    """
    return _json(
        {"error": {"message": message, "type": typ, "param": param, "code": code}},
        status=status,
    )


def _not_supported(feature: str) -> aiohttp.web.Response:
    """功能不支持的标准 501 响应。

    Args:
        feature: 功能名。

    Returns:
        Response 实例。
    """
    return _err(
        501,
        "{} is not supported by any available provider".format(feature),
        "not_implemented",
        "not_supported",
    )


def _normalize_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """规范化消息列表，处理 content 为列表的情况。

    Args:
        messages: 原始消息列表。

    Returns:
        规范化后的消息列表。
    """
    out: List[Dict[str, Any]] = []
    for m in messages:
        msg = dict(m)
        content = msg.get("content")
        if msg.get("role") == "system" and isinstance(content, list):
            msg["content"] = normalize_content(content)
        out.append(msg)
    return out


def _extract_upload_files(
    messages: List[Dict[str, Any]],
) -> List[tuple]:
    """从消息中提取需要上传的文件（base64 数据）。

    提取类型：
    - image_url 中的 data: URI
    - input_audio 中的 data URI
    - file 附件中的 data URI

    Args:
        messages: 消息列表。

    Returns:
        [(file_bytes, filename), ...] 列表。
    """
    import base64 as _b64

    upload_files: List[tuple] = []
    for msg in messages:
        content = msg.get("content", "")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            part_type = part.get("type", "")

            if part_type == "image_url":
                url = part.get("image_url", {}).get("url", "")
                if url.startswith("data:"):
                    try:
                        header, data = url.split(",", 1)
                        file_bytes = _b64.b64decode(data)
                        mime = header.split(":")[1].split(";")[0]
                        ext = _mime_to_ext(mime)
                        upload_files.append((file_bytes, "image.{}".format(ext)))
                    except (binascii.Error, ValueError, IndexError) as exc:
                        logger.warning("提取 image_url 失败: %s", exc)

            elif part_type == "video_url":
                url = part.get("video_url", {}).get("url", "")
                if url.startswith("data:"):
                    try:
                        header, data = url.split(",", 1)
                        file_bytes = _b64.b64decode(data)
                        mime = header.split(":")[1].split(";")[0]
                        ext = _mime_to_ext(mime)
                        upload_files.append((file_bytes, "video.{}".format(ext)))
                    except (binascii.Error, ValueError, IndexError) as exc:
                        logger.warning("提取 video_url 失败: %s", exc)

            elif part_type == "input_audio":
                audio = part.get("input_audio", {})
                data = audio.get("data", "")
                if data.startswith("data:"):
                    try:
                        header, b64_data = data.split(",", 1)
                        file_bytes = _b64.b64decode(b64_data)
                        mime = header.split(":")[1].split(";")[0]
                        ext = _mime_to_ext(mime)
                        upload_files.append((file_bytes, "audio.{}".format(ext)))
                    except (binascii.Error, ValueError, IndexError) as exc:
                        logger.warning("提取 input_audio 失败: %s", exc)

            elif part_type == "file":
                file_obj = part.get("file", {})
                file_data = file_obj.get("data", "")
                filename = file_obj.get("filename", "attachment")
                if file_data.startswith("data:"):
                    try:
                        header, b64_data = file_data.split(",", 1)
                        file_bytes = _b64.b64decode(b64_data)
                        logger.debug(
                            "提取文件 [%s]: %d bytes, 内容预览: %r",
                            filename,
                            len(file_bytes),
                            file_bytes[:100],
                        )
                        upload_files.append((file_bytes, filename))
                    except Exception as e:
                        logger.warning("文件提取失败 [%s]: %s", filename, e)

    return upload_files


def _mime_to_ext(mime: str) -> str:
    """MIME 类型映射到文件扩展名。

    Args:
        mime: MIME 类型字符串。

    Returns:
        文件扩展名。
    """
    mapping = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/gif": "gif",
        "image/webp": "webp",
        "image/bmp": "bmp",
        "audio/mpeg": "mp3",
        "audio/wav": "wav",
        "audio/ogg": "ogg",
        "audio/flac": "flac",
        "video/mp4": "mp4",
        "video/webm": "webm",
        "application/pdf": "pdf",
        "text/plain": "txt",
    }
    return mapping.get(mime, "bin")


def _sl(s: Optional[Union[str, List[str]]]) -> Optional[List[str]]:
    """统一 stop 参数为列表。

    Args:
        s: stop 参数。

    Returns:
        列表或 None。
    """
    if s is None:
        return None
    return [s] if isinstance(s, str) else list(s)


# _clean_fncall, _safe_flush, _get_json are imported from src.core.http


# ═══════════════════════════════════════════════════════════════════════════
# Chat Completions
# ═══════════════════════════════════════════════════════════════════════════


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

    content = _clean_fncall(content, platform_id=platform_id)

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


# ═══════════════════════════════════════════════════════════════════════════
# Responses API
# ═══════════════════════════════════════════════════════════════════════════


async def create_response(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """Responses API 端点 /v1/responses。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    from src.core import gateway

    body = await _get_json(request)
    if body is None:
        return _err(400, "Invalid JSON", "invalid_json")

    mdl = body.get("model", "")
    input_data = body.get("input", "")

    if isinstance(input_data, str):
        messages: List[Dict[str, Any]] = [{"role": "user", "content": input_data}]
    elif isinstance(input_data, list):
        messages = _normalize_messages(input_data)
    else:
        messages = [{"role": "user", "content": str(input_data)}]

    instructions = body.get("instructions")
    if instructions:
        instructions_str = normalize_content(instructions)
        if instructions_str:
            messages.insert(0, {"role": "system", "content": instructions_str})

    tools_raw = body.get("tools")
    tools: Optional[List[Dict]] = None
    if tools_raw:
        tools = [t for t in tools_raw if t.get("type") == "function"]

    cp: List[str] = []
    usage_d: Optional[Dict] = None
    try:
        async for ch in gateway.dispatch(
            registry=request.app[REGISTRY_KEY],
            messages=messages,
            model=mdl,
            stream=False,
            tools=tools,
        ):
            if isinstance(ch, str):
                cp.append(ch)
            elif isinstance(ch, dict) and "usage" in ch:
                usage_d = ch["usage"]
    except NoCandidateError as e:
        return _err(503, str(e), "no_candidate")
    except ProviderError as e:
        return _err(502, str(e), "provider_error")

    content = _clean_fncall("".join(cp))
    resp_id = "resp_{}".format(uuid.uuid4().hex[:24])

    return _json(
        {
            "id": resp_id,
            "object": "response",
            "created_at": int(time.time()),
            "model": mdl,
            "output": [
                {
                    "type": "message",
                    "id": "msg_{}".format(uuid.uuid4().hex[:16]),
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": content}],
                }
            ],
            "usage": usage_d
            or {
                "input_tokens": sum(
                    len(str(m.get("content", ""))) // 3 for m in messages
                ),
                "output_tokens": len(content) // 3,
                "total_tokens": 0,
            },
        }
    )


# ═══════════════════════════════════════════════════════════════════════════
# Embeddings
# ═══════════════════════════════════════════════════════════════════════════


async def create_embeddings(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """嵌入向量端点 /v1/embeddings。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    body = await _get_json(request)
    if body is None:
        return _err(400, "Invalid JSON", "invalid_json")

    model = body.get("model", "")
    registry = request.app[REGISTRY_KEY]
    cands = await registry.get_candidates(model=model, capability="embedding")
    if not cands:
        cands = await registry.get_candidates(capability="embedding")
    if not cands:
        return _not_supported("Embeddings")

    selected = await registry.selector.select(cands, 1)
    cand = selected[0] if selected else None
    if cand is None:
        return _not_supported("Embeddings")

    adapter = registry.adapter_for(cand)
    try:
        result = await adapter.create_embedding(
            cand,
            body.get("input", ""),
            body.get("model", ""),
            encoding_format=body.get("encoding_format", "float"),
        )
        return _json(result)
    except NotImplementedError:
        return _not_supported("Embeddings")
    except Exception as e:
        return _err(502, str(e), "provider_error")


# ═══════════════════════════════════════════════════════════════════════════
# Images
# ═══════════════════════════════════════════════════════════════════════════


async def create_image(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """图片生成端点 /v1/images/generations。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    body = await _get_json(request)
    if body is None:
        return _err(400, "Invalid JSON", "invalid_json")

    registry = request.app[REGISTRY_KEY]
    model = body.get("model", "")

    # 根据 model 参数找到支持 image_gen 的平台
    if model:
        cands = await registry.get_candidates(model)
        cand = None
        for c in cands:
            if c.image_gen:
                cand = c
                break
        if cand is None:
            return _not_supported(f"Model {model} does not support image generation")
    else:
        # 无 model 时找第一个支持 image_gen 的平台
        cand = await registry.get_capable_candidate("image_gen")
        if cand is None:
            return _not_supported("Image generation")

    adapter = registry.adapter_for(cand)
    try:
        result = await adapter.create_image(
            cand,
            body.get("prompt", ""),
            body.get("model", ""),
            **{k: v for k, v in body.items() if k not in ("prompt", "model")},
        )
        return _json(result)
    except NotImplementedError:
        return _not_supported("Image generation")
    except Exception as e:
        return _err(502, str(e), "provider_error")


async def edit_image(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """图片编辑端点 /v1/images/edits。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    registry = request.app[REGISTRY_KEY]
    cand = await registry.get_capable_candidate("image_edit")
    if cand is None:
        return _not_supported("Image editing")

    adapter = registry.adapter_for(cand)
    try:
        reader = await request.multipart()
        image_data = b""
        prompt = ""
        model = ""
        async for field in reader:
            if field.name == "image":
                image_data = await field.read()
            elif field.name == "prompt":
                prompt = (await field.read()).decode("utf-8")
            elif field.name == "model":
                model = (await field.read()).decode("utf-8")
        result = await adapter.edit_image(cand, image_data, prompt, model)
        return _json(result)
    except NotImplementedError:
        return _not_supported("Image editing")
    except Exception as e:
        return _err(502, str(e), "provider_error")


async def create_image_variation(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """图片变体端点 /v1/images/variations。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    registry = request.app[REGISTRY_KEY]
    cand = await registry.get_capable_candidate("image_variation")
    if cand is None:
        return _not_supported("Image variations")

    adapter = registry.adapter_for(cand)
    try:
        reader = await request.multipart()
        image_data = b""
        model = ""
        async for field in reader:
            if field.name == "image":
                image_data = await field.read()
            elif field.name == "model":
                model = (await field.read()).decode("utf-8")
        result = await adapter.create_image_variation(cand, image_data, model)
        return _json(result)
    except NotImplementedError:
        return _not_supported("Image variations")
    except Exception as e:
        return _err(502, str(e), "provider_error")


# ═══════════════════════════════════════════════════════════════════════════
# Audio
# ═══════════════════════════════════════════════════════════════════════════


async def create_speech(
    request: aiohttp.web.Request,
) -> Union[aiohttp.web.Response, aiohttp.web.StreamResponse]:
    """语音合成端点 /v1/audio/speech。

    Args:
        request: 请求对象。

    Returns:
        音频响应或错误响应。
    """
    body = await _get_json(request)
    if body is None:
        return _err(400, "Invalid JSON", "invalid_json")

    registry = request.app[REGISTRY_KEY]
    cand = await registry.get_capable_candidate("audio_gen")
    if cand is None:
        return _not_supported("Text-to-speech")

    adapter = registry.adapter_for(cand)
    try:
        audio_bytes = await adapter.create_speech(
            cand,
            body.get("input", ""),
            body.get("model", "tts-1"),
            body.get("voice", "alloy"),
        )
        fmt = body.get("response_format", "mp3")
        mime_map: Dict[str, str] = {
            "mp3": "audio/mpeg",
            "opus": "audio/opus",
            "aac": "audio/aac",
            "flac": "audio/flac",
            "wav": "audio/wav",
            "pcm": "audio/pcm",
        }
        return aiohttp.web.Response(
            body=audio_bytes,
            content_type=mime_map.get(fmt, "audio/mpeg"),
        )
    except NotImplementedError:
        return _not_supported("Text-to-speech")
    except Exception as e:
        return _err(502, str(e), "provider_error")


async def create_transcription(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """语音转录端点 /v1/audio/transcriptions。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    registry = request.app[REGISTRY_KEY]
    cand = await registry.get_capable_candidate("audio_transcription")
    if cand is None:
        return _not_supported("Audio transcription")

    adapter = registry.adapter_for(cand)
    try:
        reader = await request.multipart()
        audio_data = b""
        model = "whisper-1"
        async for field in reader:
            if field.name == "file":
                audio_data = await field.read()
            elif field.name == "model":
                model = (await field.read()).decode("utf-8")
        result = await adapter.create_transcription(cand, audio_data, model)
        return _json(result)
    except NotImplementedError:
        return _not_supported("Audio transcription")
    except Exception as e:
        return _err(502, str(e), "provider_error")


async def create_audio_translation(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """语音翻译端点 /v1/audio/translations。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    registry = request.app[REGISTRY_KEY]
    cand = await registry.get_capable_candidate("audio_translation")
    if cand is None:
        return _not_supported("Audio translation")

    adapter = registry.adapter_for(cand)
    try:
        reader = await request.multipart()
        audio_data = b""
        model = "whisper-1"
        async for field in reader:
            if field.name == "file":
                audio_data = await field.read()
            elif field.name == "model":
                model = (await field.read()).decode("utf-8")
        result = await adapter.create_translation(cand, audio_data, model)
        return _json(result)
    except NotImplementedError:
        return _not_supported("Audio translation")
    except Exception as e:
        return _err(502, str(e), "provider_error")


# ═══════════════════════════════════════════════════════════════════════════
# Video
# ═══════════════════════════════════════════════════════════════════════════


async def create_video(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """视频生成端点 /v1/videos/generations。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    body = await _get_json(request)
    if body is None:
        return _err(400, "Invalid JSON", "invalid_json")

    registry = request.app[REGISTRY_KEY]
    cand = await registry.get_capable_candidate("video_gen")
    if cand is None:
        return _not_supported("Video generation")

    adapter = registry.adapter_for(cand)
    try:
        result = await adapter.create_video(
            cand,
            body.get("prompt", ""),
            body.get("model", ""),
            **{k: v for k, v in body.items() if k not in ("prompt", "model")},
        )
        return _json(result)
    except NotImplementedError:
        return _not_supported("Video generation")
    except Exception as e:
        return _err(502, str(e), "provider_error")


# ═══════════════════════════════════════════════════════════════════════════
# Moderations
# ═══════════════════════════════════════════════════════════════════════════


async def create_moderation(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """内容审核端点 /v1/moderations。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    body = await _get_json(request)
    if body is None:
        return _err(400, "Invalid JSON", "invalid_json")

    registry = request.app[REGISTRY_KEY]
    cand = await registry.get_capable_candidate("moderation")
    if cand is None:
        return _not_supported("Moderations")

    adapter = registry.adapter_for(cand)
    try:
        result = await adapter.create_moderation(
            cand, body.get("input", ""), body.get("model", "")
        )
        return _json(result)
    except NotImplementedError:
        return _not_supported("Moderations")
    except Exception as e:
        return _err(502, str(e), "provider_error")


# ═══════════════════════════════════════════════════════════════════════════
# Rerank
# ═══════════════════════════════════════════════════════════════════════════


async def create_rerank(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """重排序端点 /v1/rerank。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    body = await _get_json(request)
    if body is None:
        return _err(400, "Invalid JSON", "invalid_json")

    registry = request.app[REGISTRY_KEY]
    cand = await registry.get_capable_candidate("rerank")
    if cand is None:
        return _not_supported("Rerank")

    adapter = registry.adapter_for(cand)
    try:
        result = await adapter.create_rerank(
            cand,
            body.get("query", ""),
            body.get("documents", []),
            body.get("model", ""),
        )
        return _json(result)
    except NotImplementedError:
        return _not_supported("Rerank")
    except Exception as e:
        return _err(502, str(e), "provider_error")


# ═══════════════════════════════════════════════════════════════════════════
# Files
# ═══════════════════════════════════════════════════════════════════════════


async def upload_file(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """文件上传端点 /v1/files。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    fid = _fid()
    filename = "unknown"
    purpose = "assistants"
    file_bytes = 0

    content_type = request.content_type or ""
    if "multipart" in content_type:
        try:
            reader = await request.multipart()
            async for field in reader:
                if field.name == "file":
                    data = await field.read()
                    file_bytes = len(data)
                    filename = field.filename or "unknown"
                elif field.name == "purpose":
                    purpose = (await field.read()).decode("utf-8")
        except Exception as exc:
            logger.debug("解析 multipart 上传字段失败，使用默认元数据: %s", exc)

    return _json(
        {
            "id": fid,
            "object": "file",
            "bytes": file_bytes,
            "created_at": int(time.time()),
            "filename": filename,
            "purpose": purpose,
            "status": "uploaded",
        }
    )


async def list_files(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """文件列表端点 /v1/files。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _json({"object": "list", "data": []})


async def retrieve_file(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """获取文件详情端点 /v1/files/{file_id}。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    file_id = request.match_info["file_id"]
    return _json(
        {
            "id": file_id,
            "object": "file",
            "bytes": 0,
            "created_at": int(time.time()),
            "filename": "unknown",
            "purpose": "assistants",
        }
    )


async def delete_file(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """删除文件端点 /v1/files/{file_id}。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    file_id = request.match_info["file_id"]
    return _json({"id": file_id, "object": "file", "deleted": True})


async def retrieve_file_content(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """获取文件内容端点 /v1/files/{file_id}/content。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _err(404, "File not found", "file_not_found")


# ═══════════════════════════════════════════════════════════════════════════
# Fine-tuning
# ═══════════════════════════════════════════════════════════════════════════


async def create_fine_tuning_job(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """创建微调任务端点 /v1/fine_tuning/jobs。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _not_supported("Fine-tuning")


async def list_fine_tuning_jobs(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """微调任务列表端点 /v1/fine_tuning/jobs。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _json({"object": "list", "data": []})


async def retrieve_fine_tuning_job(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """获取微调任务详情端点 /v1/fine_tuning/jobs/{job_id}。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _err(404, "Job not found", "job_not_found")


async def cancel_fine_tuning_job(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """取消微调任务端点 /v1/fine_tuning/jobs/{job_id}/cancel。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _err(404, "Job not found", "job_not_found")


async def list_fine_tuning_events(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """微调任务事件列表端点 /v1/fine_tuning/jobs/{job_id}/events。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _json({"object": "list", "data": []})


# ═══════════════════════════════════════════════════════════════════════════
# Batch
# ═══════════════════════════════════════════════════════════════════════════


async def create_batch(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """创建批处理任务端点 /v1/batches。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _not_supported("Batch")


async def list_batches(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """批处理任务列表端点 /v1/batches。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _json({"object": "list", "data": []})


async def retrieve_batch(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """获取批处理任务详情端点 /v1/batches/{batch_id}。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _err(404, "Batch not found", "batch_not_found")


async def cancel_batch(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """取消批处理任务端点 /v1/batches/{batch_id}/cancel。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _err(404, "Batch not found", "batch_not_found")


# ═══════════════════════════════════════════════════════════════════════════
# Assistants
# ═══════════════════════════════════════════════════════════════════════════


async def create_assistant(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """创建助手端点 /v1/assistants。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    body = await _get_json(request) or {}
    return _json(
        {
            "id": _aid(),
            "object": "assistant",
            "created_at": int(time.time()),
            "name": body.get("name"),
            "description": body.get("description"),
            "model": body.get("model", ""),
            "instructions": body.get("instructions"),
            "tools": body.get("tools", []),
            "metadata": body.get("metadata", {}),
        }
    )


async def list_assistants(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """助手列表端点 /v1/assistants。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _json({"object": "list", "data": []})


async def retrieve_assistant(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """获取助手详情端点 /v1/assistants/{assistant_id}。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _err(404, "Assistant not found", "assistant_not_found")


async def modify_assistant(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """修改助手端点 /v1/assistants/{assistant_id}。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _err(404, "Assistant not found", "assistant_not_found")


async def delete_assistant(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """删除助手端点 /v1/assistants/{assistant_id}。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    assistant_id = request.match_info["assistant_id"]
    return _json(
        {
            "id": assistant_id,
            "object": "assistant.deleted",
            "deleted": True,
        }
    )


# ═══════════════════════════════════════════════════════════════════════════
# Threads
# ═══════════════════════════════════════════════════════════════════════════


async def create_thread(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """创建线程端点 /v1/threads。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _json(
        {
            "id": _tid(),
            "object": "thread",
            "created_at": int(time.time()),
            "metadata": {},
        }
    )


async def retrieve_thread(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """获取线程详情端点 /v1/threads/{thread_id}。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    thread_id = request.match_info["thread_id"]
    return _json(
        {
            "id": thread_id,
            "object": "thread",
            "created_at": int(time.time()),
            "metadata": {},
        }
    )


async def modify_thread(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """修改线程端点 /v1/threads/{thread_id}。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    thread_id = request.match_info["thread_id"]
    return _json(
        {
            "id": thread_id,
            "object": "thread",
            "created_at": int(time.time()),
            "metadata": {},
        }
    )


async def delete_thread(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """删除线程端点 /v1/threads/{thread_id}。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    thread_id = request.match_info["thread_id"]
    return _json({"id": thread_id, "object": "thread.deleted", "deleted": True})


async def create_thread_message(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """创建线程消息端点 /v1/threads/{thread_id}/messages。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    thread_id = request.match_info["thread_id"]
    body = await _get_json(request) or {}
    return _json(
        {
            "id": "msg_{}".format(uuid.uuid4().hex[:24]),
            "object": "thread.message",
            "created_at": int(time.time()),
            "thread_id": thread_id,
            "role": body.get("role", "user"),
            "content": [
                {
                    "type": "text",
                    "text": {
                        "value": normalize_content(body.get("content", "")),
                        "annotations": [],
                    },
                }
            ],
            "metadata": body.get("metadata", {}),
        }
    )


async def list_thread_messages(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """线程消息列表端点 /v1/threads/{thread_id}/messages。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _json({"object": "list", "data": []})


# ═══════════════════════════════════════════════════════════════════════════
# Runs
# ═══════════════════════════════════════════════════════════════════════════


async def create_run(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """创建运行端点 /v1/threads/{thread_id}/runs。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    thread_id = request.match_info["thread_id"]
    body = await _get_json(request) or {}
    return _json(
        {
            "id": _rid(),
            "object": "thread.run",
            "created_at": int(time.time()),
            "thread_id": thread_id,
            "assistant_id": body.get("assistant_id", ""),
            "status": "queued",
            "model": body.get("model", ""),
            "instructions": body.get("instructions"),
            "tools": body.get("tools", []),
            "metadata": body.get("metadata", {}),
        }
    )


async def list_runs(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """运行列表端点 /v1/threads/{thread_id}/runs。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _json({"object": "list", "data": []})


async def retrieve_run(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """获取运行详情端点 /v1/threads/{thread_id}/runs/{run_id}。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    thread_id = request.match_info["thread_id"]
    run_id = request.match_info["run_id"]
    return _json(
        {
            "id": run_id,
            "object": "thread.run",
            "created_at": int(time.time()),
            "thread_id": thread_id,
            "status": "completed",
            "model": "",
        }
    )


async def cancel_run(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """取消运行端点 /v1/threads/{thread_id}/runs/{run_id}/cancel。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    thread_id = request.match_info["thread_id"]
    run_id = request.match_info["run_id"]
    return _json(
        {
            "id": run_id,
            "object": "thread.run",
            "status": "cancelled",
            "thread_id": thread_id,
        }
    )


async def submit_tool_outputs(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """提交工具输出端点 /v1/threads/{thread_id}/runs/{run_id}/submit_tool_outputs。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    thread_id = request.match_info["thread_id"]
    run_id = request.match_info["run_id"]
    return _json(
        {
            "id": run_id,
            "object": "thread.run",
            "status": "completed",
            "thread_id": thread_id,
        }
    )


# ═══════════════════════════════════════════════════════════════════════════
# Vector Stores
# ═══════════════════════════════════════════════════════════════════════════


async def create_vector_store(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """创建向量存储端点 /v1/vector_stores。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    body = await _get_json(request) or {}
    return _json(
        {
            "id": _vid(),
            "object": "vector_store",
            "created_at": int(time.time()),
            "name": body.get("name", ""),
            "usage_bytes": 0,
            "file_counts": {
                "in_progress": 0,
                "completed": 0,
                "failed": 0,
                "cancelled": 0,
                "total": 0,
            },
            "status": "completed",
            "metadata": body.get("metadata", {}),
        }
    )


async def list_vector_stores(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """向量存储列表端点 /v1/vector_stores。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _json({"object": "list", "data": []})


async def retrieve_vector_store(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """获取向量存储详情端点 /v1/vector_stores/{store_id}。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _err(404, "Vector store not found", "not_found")


async def delete_vector_store(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """删除向量存储端点 /v1/vector_stores/{store_id}。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    store_id = request.match_info["store_id"]
    return _json({"id": store_id, "object": "vector_store.deleted", "deleted": True})


async def create_vector_store_file(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """向量存储文件关联端点 /v1/vector_stores/{store_id}/files。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    store_id = request.match_info["store_id"]
    return _json(
        {
            "id": _fid(),
            "object": "vector_store.file",
            "created_at": int(time.time()),
            "vector_store_id": store_id,
            "status": "completed",
        }
    )


async def list_vector_store_files(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """向量存储文件列表端点 /v1/vector_stores/{store_id}/files。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _json({"object": "list", "data": []})


# ═══════════════════════════════════════════════════════════════════════════
# Uploads
# ═══════════════════════════════════════════════════════════════════════════


async def create_upload(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """创建上传端点 /v1/uploads。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    body = await _get_json(request) or {}
    return _json(
        {
            "id": _uid(),
            "object": "upload",
            "bytes": body.get("bytes", 0),
            "created_at": int(time.time()),
            "filename": body.get("filename", ""),
            "purpose": body.get("purpose", ""),
            "status": "pending",
        }
    )


async def add_upload_part(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """添加上传分片端点 /v1/uploads/{upload_id}/parts。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    upload_id = request.match_info["upload_id"]
    return _json(
        {
            "id": "part_{}".format(uuid.uuid4().hex[:16]),
            "object": "upload.part",
            "created_at": int(time.time()),
            "upload_id": upload_id,
        }
    )


async def complete_upload(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """完成上传端点 /v1/uploads/{upload_id}/complete。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    upload_id = request.match_info["upload_id"]
    return _json(
        {
            "id": upload_id,
            "object": "upload",
            "status": "completed",
            "file": {
                "id": _fid(),
                "object": "file",
                "created_at": int(time.time()),
            },
        }
    )


async def cancel_upload(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """取消上传端点 /v1/uploads/{upload_id}/cancel。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    upload_id = request.match_info["upload_id"]
    return _json({"id": upload_id, "object": "upload", "status": "cancelled"})


# ═══════════════════════════════════════════════════════════════════════════
# 路由注册
# ═══════════════════════════════════════════════════════════════════════════


def setup_routes(app: aiohttp.web.Application) -> None:
    """注册所有 OpenAI 兼容路由。

    Args:
        app: aiohttp.web.Application 实例。
    """
    app.router.add_route("*", "/v1/chat/completions", chat_completions)
    app.router.add_post("/v1/responses", create_response)
    app.router.add_post("/v1/embeddings", create_embeddings)
    app.router.add_post("/v1/images/generations", create_image)
    app.router.add_post("/v1/images/edits", edit_image)
    app.router.add_post("/v1/images/variations", create_image_variation)
    app.router.add_post("/v1/audio/speech", create_speech)
    app.router.add_post("/v1/audio/transcriptions", create_transcription)
    app.router.add_post("/v1/audio/translations", create_audio_translation)
    app.router.add_post("/v1/videos/generations", create_video)
    app.router.add_post("/v1/moderations", create_moderation)
    app.router.add_post("/v1/rerank", create_rerank)
    app.router.add_post("/v1/files", upload_file)
    app.router.add_get("/v1/files", list_files)
    app.router.add_get("/v1/files/{file_id}", retrieve_file)
    app.router.add_delete("/v1/files/{file_id}", delete_file)
    app.router.add_get("/v1/files/{file_id}/content", retrieve_file_content)
    app.router.add_post("/v1/fine_tuning/jobs", create_fine_tuning_job)
    app.router.add_get("/v1/fine_tuning/jobs", list_fine_tuning_jobs)
    app.router.add_get("/v1/fine_tuning/jobs/{job_id}", retrieve_fine_tuning_job)
    app.router.add_post("/v1/fine_tuning/jobs/{job_id}/cancel", cancel_fine_tuning_job)
    app.router.add_get("/v1/fine_tuning/jobs/{job_id}/events", list_fine_tuning_events)
    app.router.add_post("/v1/batches", create_batch)
    app.router.add_get("/v1/batches", list_batches)
    app.router.add_get("/v1/batches/{batch_id}", retrieve_batch)
    app.router.add_post("/v1/batches/{batch_id}/cancel", cancel_batch)
    app.router.add_post("/v1/assistants", create_assistant)
    app.router.add_get("/v1/assistants", list_assistants)
    app.router.add_get("/v1/assistants/{assistant_id}", retrieve_assistant)
    app.router.add_post("/v1/assistants/{assistant_id}", modify_assistant)
    app.router.add_delete("/v1/assistants/{assistant_id}", delete_assistant)
    app.router.add_post("/v1/threads", create_thread)
    app.router.add_get("/v1/threads/{thread_id}", retrieve_thread)
    app.router.add_post("/v1/threads/{thread_id}", modify_thread)
    app.router.add_delete("/v1/threads/{thread_id}", delete_thread)
    app.router.add_post("/v1/threads/{thread_id}/messages", create_thread_message)
    app.router.add_get("/v1/threads/{thread_id}/messages", list_thread_messages)
    app.router.add_post("/v1/threads/{thread_id}/runs", create_run)
    app.router.add_get("/v1/threads/{thread_id}/runs", list_runs)
    app.router.add_get("/v1/threads/{thread_id}/runs/{run_id}", retrieve_run)
    app.router.add_post("/v1/threads/{thread_id}/runs/{run_id}/cancel", cancel_run)
    app.router.add_post(
        "/v1/threads/{thread_id}/runs/{run_id}/submit_tool_outputs", submit_tool_outputs
    )
    app.router.add_post("/v1/vector_stores", create_vector_store)
    app.router.add_get("/v1/vector_stores", list_vector_stores)
    app.router.add_get("/v1/vector_stores/{store_id}", retrieve_vector_store)
    app.router.add_delete("/v1/vector_stores/{store_id}", delete_vector_store)
    app.router.add_post("/v1/vector_stores/{store_id}/files", create_vector_store_file)
    app.router.add_get("/v1/vector_stores/{store_id}/files", list_vector_store_files)
    app.router.add_post("/v1/uploads", create_upload)
    app.router.add_post("/v1/uploads/{upload_id}/parts", add_upload_part)
    app.router.add_post("/v1/uploads/{upload_id}/complete", complete_upload)
    app.router.add_post("/v1/uploads/{upload_id}/cancel", cancel_upload)
