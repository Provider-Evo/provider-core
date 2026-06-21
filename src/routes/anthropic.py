from __future__ import annotations

"""Anthropic 兼容路由——aiohttp.web 实现"""

import asyncio
import json
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

import aiohttp.web
from src.core.server import REGISTRY_KEY, json_response
from src.core.errors import NoCandidateError, ProviderError
from src.core.tools import normalize_content, parse_fncall_xml
from src.core.server import (
    clean_fncall as _clean_fncall,
    get_json as _get_json,
    safe_flush as _safe_flush,
)
from src.logger import get_logger
from src.core.config.resolver import resolve_model

__all__ = ["setup_routes"]
logger = get_logger(__name__)

# fncall 标签常量（避免字符串拼接被工具误识别）
_FNCALL_OPEN_TAG = "<function_calls>"
_FNCALL_CLOSE_TAG = "</function_calls>"

# Pre-compiled regex for _clean_fncall (avoid recompilation on every call)

# ═══════════════════════════════════════════════════════════════════════════
# ID 生成工具
# ═══════════════════════════════════════════════════════════════════════════


def _mid() -> str:
    return "msg_{}".format(uuid.uuid4().hex[:24])


def _tc_id() -> str:
    return "toolu_{}".format(uuid.uuid4().hex[:24])


# ═══════════════════════════════════════════════════════════════════════════
# HTTP 响应构建工具
# ═══════════════════════════════════════════════════════════════════════════


def _json(data: Any, status: int = 200) -> aiohttp.web.Response:
    return json_response(data, status=status)


def _err(
    status: int,
    message: str,
    error_type: str = "server_error",
) -> aiohttp.web.Response:
    """构建 Anthropic 格式错误响应。

    Args:
        status: HTTP 状态码。
        message: 错误信息。
        error_type: Anthropic 错误类型字符串。

    Returns:
        Response 实例。
    """
    return _json(
        {
            "type": "error",
            "error": {"type": error_type, "message": message},
        },
        status=status,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 内容规范化工具
# ═══════════════════════════════════════════════════════════════════════════


def _normalize_anth_content(content: Any) -> Optional[str]:
    """规范化 Anthropic system/content 字段为字符串。

    处理以下类型：
    - None → None
    - str → str（原样返回）
    - list → 提取所有 type=text 的文本，换行拼接
    - 其他 → str() 强转

    Args:
        content: 原始 content 字段值。

    Returns:
        规范化字符串，内容为空时返回 None。
    """
    if content is None:
        return None
    if isinstance(content, str):
        return content or None
    if isinstance(content, list):
        texts: List[str] = []
        for item in content:
            if isinstance(item, dict):
                item_type = item.get("type", "")
                if item_type == "text":
                    text = item.get("text", "")
                    if text:
                        texts.append(text)
                elif "text" in item:
                    # 兼容非标准格式（直接含 text 字段）
                    text = item.get("text", "")
                    if text:
                        texts.append(text)
            elif isinstance(item, str) and item:
                texts.append(item)
        return "\n".join(texts) if texts else None
    result = str(content)
    return result if result else None


def _extract_image_source(image_block: Dict[str, Any]) -> str:
    """从 Anthropic image block 提取可读描述。

    Args:
        image_block: Anthropic image content block。

    Returns:
        图片描述字符串。
    """
    source = image_block.get("source", {})
    source_type = source.get("type", "")
    if source_type == "url":
        return "[image: {}]".format(source.get("url", "unknown"))
    if source_type == "base64":
        media_type = source.get("media_type", "image")
        return "[image: base64 {} data]".format(media_type)
    return "[image]"


def _content_block_to_text(block: Dict[str, Any]) -> str:
    """将单个 Anthropic content block 转换为文本描述。

    Args:
        block: Anthropic content block 字典。

    Returns:
        文本描述字符串。
    """
    btype = block.get("type", "")
    if btype == "text":
        return block.get("text", "")
    if btype == "image":
        return _extract_image_source(block)
    if btype == "tool_result":
        tool_content = block.get("content", block.get("text", ""))
        tool_id = block.get("tool_use_id", "")
        content_str = normalize_content(tool_content) if tool_content else ""
        return "Tool result ({}): {}".format(tool_id, content_str)
    if btype == "tool_use":
        tool_id = block.get("id", "")
        name = block.get("name", "")
        inp = block.get("input", {})
        inp_str = (
            json.dumps(inp, ensure_ascii=False)
            if isinstance(inp, dict)
            else str(inp)
        )
        return "Tool call ({}): {}({})".format(tool_id, name, inp_str)
    if btype == "thinking":
        return "[thinking: {}]".format(block.get("thinking", ""))
    # 未知类型，尝试提取 text
    return block.get("text", str(block))


def _anth_content_to_openai(
    content: Any,
) -> Union[str, List[Dict[str, Any]]]:
    """将 Anthropic content 转换为 OpenAI content 格式。

    支持视觉多模态：image block 转换为 OpenAI image_url 格式。
    纯文本场景返回字符串，含图片时返回 content list。

    Args:
        content: Anthropic content 字段（str 或 list）。

    Returns:
        OpenAI 兼容的 content（字符串或列表）。
    """
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content)

    has_image = any(
        isinstance(b, dict) and b.get("type") == "image" for b in content
    )

    if not has_image:
        # 纯文本，拼接为字符串
        parts: List[str] = []
        for block in content:
            if isinstance(block, dict):
                parts.append(_content_block_to_text(block))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(filter(None, parts))

    # 含图片，构建 OpenAI multipart content list
    result_blocks: List[Dict[str, Any]] = []
    for block in content:
        if not isinstance(block, dict):
            if isinstance(block, str) and block:
                result_blocks.append({"type": "text", "text": block})
            continue

        btype = block.get("type", "")
        if btype == "text":
            text = block.get("text", "")
            if text:
                result_blocks.append({"type": "text", "text": text})
        elif btype == "image":
            source = block.get("source", {})
            source_type = source.get("type", "")
            if source_type == "url":
                result_blocks.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": source.get("url", "")},
                    }
                )
            elif source_type == "base64":
                media_type = source.get("media_type", "image/jpeg")
                data = source.get("data", "")
                result_blocks.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:{};base64,{}".format(
                                media_type, data
                            )
                        },
                    }
                )
        else:
            text = _content_block_to_text(block)
            if text:
                result_blocks.append({"type": "text", "text": text})

    return result_blocks if result_blocks else ""


def _anth_messages_to_openai(
    messages: List[Dict[str, Any]],
    system: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """将 Anthropic 格式 messages 转换为 OpenAI 格式。

    保留多模态结构（图片）；其余 block 类型降级为文本描述。

    Args:
        messages: Anthropic 格式消息列表。
        system: system prompt 字符串，不为 None 时前置插入。

    Returns:
        OpenAI 格式消息列表（新列表，原列表不变）。
    """
    out: List[Dict[str, Any]] = []
    if system:
        out.append({"role": "system", "content": system})

    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        converted = _anth_content_to_openai(content)
        out.append({"role": role, "content": converted})

    # 防御性检查：确保消息列表不为空
    if not out:
        out.append({"role": "user", "content": ""})

    return out


def _anth_tools_to_openai(
    tools: Optional[List[Dict[str, Any]]],
) -> Optional[List[Dict[str, Any]]]:
    """将 Anthropic 格式工具转换为 OpenAI 格式。

    Args:
        tools: Anthropic 工具列表。

    Returns:
        OpenAI 格式工具列表，输入为空时返回 None。
    """
    if not tools:
        return None
    result: List[Dict[str, Any]] = []
    for t in tools:
        result.append(
            {
                "type": "function",
                "function": {
                    "name": t.get("name", ""),
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {}),
                },
            }
        )
    return result or None


def _is_thinking(body: Dict[str, Any]) -> bool:
    """判断请求是否开启 thinking 模式。

    支持以下格式：
    - thinking: true/false（布尔）
    - thinking: {"type": "enabled"}（Anthropic 标准格式）
    - thinking: {"enabled": true}（扩展格式）

    Args:
        body: 请求体字典。

    Returns:
        是否开启 thinking。
    """
    t = body.get("thinking")
    if t is None:
        return False
    if isinstance(t, bool):
        return t
    if isinstance(t, dict):
        return (
            t.get("type") == "enabled"
            or bool(t.get("enabled", False))
        )
    return bool(t)


# ═══════════════════════════════════════════════════════════════════════════
# fncall 处理工具（与 openai.py 对齐）
# ═══════════════════════════════════════════════════════════════════════════


def _openai_tc_to_anth(
    tc: Dict[str, Any],
) -> Dict[str, Any]:
    """将 OpenAI tool_call 转换为 Anthropic tool_use content block。

    id 必须以 toolu_ 开头；若上游 id 不符合，生成新的合规 id。

    Args:
        tc: OpenAI tool_call 字典。

    Returns:
        Anthropic tool_use block 字典。
    """
    func = tc.get("function", {})
    args_raw = func.get("arguments", "{}")
    # arguments 可能是 dict（来自 gateway）或 JSON 字符串
    if isinstance(args_raw, dict):
        inp = args_raw
    else:
        try:
            inp = json.loads(args_raw)
        except (json.JSONDecodeError, ValueError):
            inp = {}

    raw_id: str = tc.get("id") or ""
    tool_id = raw_id if raw_id.startswith("toolu_") else _tc_id()

    return {
        "type": "tool_use",
        "id": tool_id,
        "name": func.get("name", ""),
        "input": inp,
    }


def _build_dispatch_kwargs(
    body: Dict[str, Any],
    messages: List[Dict[str, Any]],
    stream: bool,
    registry: Any,
    tools: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """构建 gateway.dispatch 调用参数。

    Args:
        body: 请求体字典。
        messages: 已转换的 OpenAI 格式消息列表。
        stream: 是否流式。
        registry: provider 注册表。
        tools: 已转换的 OpenAI 格式工具列表。

    Returns:
        dispatch 关键字参数字典。
    """
    stop = body.get("stop_sequences")
    if stop is not None and isinstance(stop, list):
        stop_val: Optional[List[str]] = stop
    elif stop is not None:
        stop_val = [str(stop)]
    else:
        stop_val = None

    return {
        "registry": registry,
        "messages": messages,
        "model": resolve_model(body.get("model", ""), "anthropic"),
        "stream": stream,
        "tools": tools,
        "thinking": _is_thinking(body),
        "search": bool(body.get("search", False)),
        "temperature": body.get("temperature"),
        "top_p": body.get("top_p"),
        "max_tokens": body.get("max_tokens", 4096),
        "stop": stop_val,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 流式写入工具
# ═══════════════════════════════════════════════════════════════════════════


async def _write_event(
    resp: aiohttp.web.StreamResponse,
    event: str,
    data: Dict[str, Any],
) -> None:
    """向流式响应写入一个 Anthropic SSE 事件。

    Args:
        resp: 流式响应对象。
        event: 事件名称。
        data: 事件数据字典。
    """
    line = "event: {}\ndata: {}\n\n".format(
        event, json.dumps(data, ensure_ascii=False)
    )
    try:
        await resp.write(line.encode("utf-8"))
    except (ConnectionError, OSError) as exc:
        logger.warning("SSE 事件写入失败: %s", exc)


# ═══════════════════════════════════════════════════════════════════════════
# 流式消息生成
# ═══════════════════════════════════════════════════════════════════════════


async def _stream_messages(
    request: aiohttp.web.Request,
    body: Dict[str, Any],
    msgs: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]],
    thinking: bool,
) -> aiohttp.web.StreamResponse:
    """Anthropic 流式消息生成核心实现。

    按 Anthropic SSE 规范输出事件序列：
    message_start → content_block_start → content_block_delta(s)
    → content_block_stop → [tool_use blocks] → message_delta → message_stop

    Args:
        request: 请求对象。
        body: 已解析的请求体。
        msgs: 已转换的 OpenAI 格式消息列表。
        tools: 已转换的 OpenAI 格式工具列表。
        thinking: 是否开启 thinking 模式。

    Returns:
        StreamResponse 实例。
    """
    from src.core import gateway

    mid = _mid()
    mdl = resolve_model(body.get("model", ""), "anthropic")
    pt = sum(len(str(m.get("content", ""))) // 3 for m in msgs)

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

    # message_start
    await _write_event(
        resp,
        "message_start",
        {
            "type": "message_start",
            "message": {
                "id": mid,
                "type": "message",
                "role": "assistant",
                "content": [],
                "model": mdl,
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": pt, "output_tokens": 1},
            },
        },
    )

    # ping（Anthropic 标准流开头）
    await _write_event(resp, "ping", {"type": "ping"})

    # content block 索引管理
    block_idx = 0

    # thinking block（若开启且无工具调用，避免冲突）
    effective_thinking = thinking and not tools
    if effective_thinking:
        await _write_event(
            resp,
            "content_block_start",
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "thinking", "thinking": ""},
            },
        )
        block_idx = 1

    # 主文本 block 索引；effective_thinking=True 时延迟开启，确保顺序正确
    text_block_idx = block_idx
    if not effective_thinking:
        await _write_event(
            resp,
            "content_block_start",
            {
                "type": "content_block_start",
                "index": text_block_idx,
                "content_block": {"type": "text", "text": ""},
            },
        )

    # 状态变量
    platform_id = ""        # 从 _meta 获取的平台 ID，用于协议感知
    text_buffer = ""       # 普通文本缓冲（检测 fncall 前缀）
    fncall_buffer = ""     # fncall XML 累积缓冲
    in_fncall = False       # 是否已进入 fncall 累积模式
    buffered_text_chunks: List[str] = []
    tool_calls_data: List[Dict[str, Any]] = []
    usage_d: Optional[Dict[str, Any]] = None
    output_tokens = 0

    async def _emit_text_delta_chunk(chunk: str) -> None:
        """处理并输出单个文本分片。"""
        nonlocal text_buffer, fncall_buffer, in_fncall, platform_id

        if in_fncall:
            fncall_buffer += chunk
            return

        text_buffer += chunk

        # 协议感知的标签检测
        from src.core.fncall.registry import get_protocol
        proto = get_protocol(platform_id=platform_id)
        trigger_tags = proto.get_trigger_tags()

        tag_idx = -1
        for tag in trigger_tags:
            idx = text_buffer.find(tag)
            if idx != -1 and (tag_idx == -1 or idx < tag_idx):
                tag_idx = idx
        if tag_idx != -1:
            safe_part = text_buffer[:tag_idx]
            if safe_part:
                _log_chunks = request.get("_req_log_chunks")
                if _log_chunks is not None:
                    _log_chunks.append(safe_part)
                await _write_event(
                    resp,
                    "content_block_delta",
                    {
                        "type": "content_block_delta",
                        "index": text_block_idx,
                        "delta": {
                            "type": "text_delta",
                            "text": safe_part,
                        },
                    },
                )
            fncall_buffer = text_buffer[tag_idx:]
            text_buffer = ""
            in_fncall = True
            return

        # 提取安全可输出部分
        safe_part, text_buffer = _safe_flush(text_buffer, platform_id=platform_id)
        if safe_part:
            _log_chunks = request.get("_req_log_chunks")
            if _log_chunks is not None:
                _log_chunks.append(safe_part)
            await _write_event(
                resp,
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": text_block_idx,
                    "delta": {
                        "type": "text_delta",
                        "text": safe_part,
                    },
                },
            )

    try:
        async for ch in gateway.dispatch(
            **_build_dispatch_kwargs(body, msgs, True, request.app[REGISTRY_KEY], tools)
        ):
            if isinstance(ch, str):
                output_tokens += 1
                if effective_thinking:
                    buffered_text_chunks.append(ch)
                else:
                    await _emit_text_delta_chunk(ch)

            elif isinstance(ch, dict):
                if "_meta" in ch:
                    platform_id = ch["_meta"].get("platform", "")
                    if platform_id:
                        resp._platform = platform_id
                elif "thinking" in ch and effective_thinking:
                    thinking_text = ch["thinking"]
                    # 分块输出 thinking_delta，固定步长 20 字符
                    _THINKING_CHUNK = 20
                    for _t_off in range(
                        0, max(1, len(thinking_text)), _THINKING_CHUNK
                    ):
                        _t_chunk = thinking_text[_t_off: _t_off + _THINKING_CHUNK]
                        await _write_event(
                            resp,
                            "content_block_delta",
                            {
                                "type": "content_block_delta",
                                "index": 0,
                                "delta": {
                                    "type": "thinking_delta",
                                    "thinking": _t_chunk,
                                },
                            },
                        )
                elif "tool_calls" in ch:
                    tool_calls_data = ch["tool_calls"]
                elif "usage" in ch:
                    usage_d = ch["usage"]

    except asyncio.CancelledError:
        return resp
    except ConnectionResetError:
        return resp
    except NoCandidateError as exc:
        logger.warning("Anthropic 流式请求无候选项: %s", exc)
        await _write_event(
            resp,
            "error",
            {
                "type": "error",
                "error": {"type": "overloaded_error", "message": str(exc)},
            },
        )
        return resp
    except ProviderError as exc:
        logger.warning("Anthropic 流式 Provider 错误: %s", exc)
        await _write_event(
            resp,
            "error",
            {
                "type": "error",
                "error": {"type": "api_error", "message": str(exc)},
            },
        )
        return resp
    except Exception as exc:
        logger.error("Anthropic 流式错误: %s", exc, exc_info=True)
        await _write_event(
            resp,
            "error",
            {
                "type": "error",
                "error": {"type": "server_error", "message": str(exc)},
            },
        )
        return resp

    # effective_thinking 模式：先完整结束 thinking，再开始 text
    if effective_thinking:
        await _write_event(
            resp,
            "content_block_stop",
            {"type": "content_block_stop", "index": 0},
        )
        await _write_event(
            resp,
            "content_block_start",
            {
                "type": "content_block_start",
                "index": text_block_idx,
                "content_block": {"type": "text", "text": ""},
            },
        )
        for _text_chunk in buffered_text_chunks:
            await _emit_text_delta_chunk(_text_chunk)

    # 输出文本缓冲剩余
    if text_buffer and not in_fncall:
        await _write_event(
            resp,
            "content_block_delta",
            {
                "type": "content_block_delta",
                "index": text_block_idx,
                "delta": {"type": "text_delta", "text": text_buffer},
            },
        )

    # 解析 fncall buffer（如果尚未通过 tool_calls 获得）
    if in_fncall and fncall_buffer and not tool_calls_data:
        tool_calls_data = parse_fncall_xml(fncall_buffer, tools)

    # content_block_stop：文本 block
    await _write_event(
        resp,
        "content_block_stop",
        {"type": "content_block_stop", "index": text_block_idx},
    )

    # tool_use blocks（按 Anthropic 规范逐个输出）
    next_block_idx = text_block_idx + 1
    for i, tc in enumerate(tool_calls_data):
        ti = next_block_idx + i
        anth_tc = _openai_tc_to_anth(tc)
        # arguments 字符串（用于 input_json_delta）
        args_raw = tc.get("function", {}).get("arguments", "{}")
        if isinstance(args_raw, dict):
            args_str = json.dumps(args_raw, ensure_ascii=False)
        else:
            args_str = str(args_raw)

        await _write_event(
            resp,
            "content_block_start",
            {
                "type": "content_block_start",
                "index": ti,
                "content_block": {
                    "type": "tool_use",
                    "id": anth_tc["id"],
                    "name": anth_tc["name"],
                    "input": {},
                },
            },
        )
        # 按固定步长 20 字符分块输出 input_json_delta
        _JSON_CHUNK = 20
        for _j_off in range(0, max(1, len(args_str)), _JSON_CHUNK):
            _j_chunk = args_str[_j_off: _j_off + _JSON_CHUNK]
            await _write_event(
                resp,
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": ti,
                    "delta": {
                        "type": "input_json_delta",
                        "partial_json": _j_chunk,
                    },
                },
            )
        await _write_event(
            resp,
            "content_block_stop",
            {"type": "content_block_stop", "index": ti},
        )

    # message_delta（stop_reason + usage）
    stop_reason = "tool_use" if tool_calls_data else "end_turn"
    ou = output_tokens
    if usage_d:
        ou = (
            usage_d.get("completion_tokens")
            or usage_d.get("output_tokens")
            or output_tokens
        )

    await _write_event(
        resp,
        "message_delta",
        {
            "type": "message_delta",
            "delta": {
                "stop_reason": stop_reason,
                "stop_sequence": None,
            },
            "usage": {"output_tokens": ou},
        },
    )

    # message_stop
    await _write_event(resp, "message_stop", {"type": "message_stop"})

    return resp


# ═══════════════════════════════════════════════════════════════════════════
# 非流式内容收集
# ═══════════════════════════════════════════════════════════════════════════


async def _collect_messages(
    body: Dict[str, Any],
    msgs: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]],
    registry: Any,
) -> Tuple[
    str,
    List[str],
    List[Dict[str, Any]],
    Optional[Dict[str, Any]],
    str,
]:
    """收集非流式消息生成的全部输出。

    Args:
        body: 请求体字典。
        msgs: 已转换的 OpenAI 格式消息列表。
        tools: 已转换的 OpenAI 格式工具列表。
        registry: provider 注册表。

    Returns:
        (content, thinking_parts, tool_calls, usage_d) 四元组。

    Raises:
        NoCandidateError: 无可用 provider。
        ProviderError: provider 返回错误。
        Exception: 其他异常。
    """
    from src.core import gateway

    content_parts: List[str] = []
    thinking_parts: List[str] = []
    tool_calls: List[Dict[str, Any]] = []
    usage_d: Optional[Dict[str, Any]] = None
    platform_id = ""

    async for ch in gateway.dispatch(
        **_build_dispatch_kwargs(body, msgs, False, registry, tools)
    ):
        if isinstance(ch, str):
            content_parts.append(ch)
        elif isinstance(ch, dict):
            if "_meta" in ch:
                platform_id = ch["_meta"].get("platform", "")
            elif "thinking" in ch:
                thinking_parts.append(ch["thinking"])
            elif "tool_calls" in ch:
                tool_calls = ch["tool_calls"]
            elif "usage" in ch:
                usage_d = ch["usage"]

    # 清理文本中残留的 fncall 标签
    raw_content = "".join(content_parts)
    cleaned = _clean_fncall(raw_content, platform_id=platform_id)

    # 若已有结构化 tool_calls，清空文本
    if tool_calls:
        cleaned = ""
    else:
        from src.core.fncall.registry import get_protocol
        proto = get_protocol(platform_id=platform_id)
        trigger_tags = proto.get_trigger_tags()
        has_trigger = any(tag in raw_content for tag in trigger_tags)
        if has_trigger:
            # 文本中含有 fncall 标签，尝试解析
            parsed = parse_fncall_xml(raw_content, tools)
            if parsed:
                tool_calls = parsed
                cleaned = ""

    return cleaned, thinking_parts, tool_calls, usage_d, platform_id


# ═══════════════════════════════════════════════════════════════════════════
# 路由处理器
# ═══════════════════════════════════════════════════════════════════════════


async def messages_handler(
    request: aiohttp.web.Request,
) -> aiohttp.web.StreamResponse:
    """Anthropic Messages 端点处理器 POST /v1/messages & POST /messages。

    完整支持：
    - 流式 / 非流式
    - thinking 模式
    - 工具调用（tool_use blocks）
    - 多模态内容（image blocks）
    - stop_sequences 透传

    Args:
        request: 请求对象。

    Returns:
        流式或非流式响应对象。
    """
    body = await _get_json(request)
    if body is None:
        return _err(400, "Invalid JSON in request body", "invalid_request_error")

    messages_raw = body.get("messages", [])
    if not messages_raw:
        return _err(400, "messages is required", "invalid_request_error")

    mdl = body.get("model", "")
    if not mdl:
        return _err(400, "model is required", "invalid_request_error")

    # 解析模型别名
    mdl = resolve_model(mdl, "anthropic")

    # 统一预处理
    system_str = _normalize_anth_content(body.get("system"))
    msgs = _anth_messages_to_openai(messages_raw, system_str)
    tools = _anth_tools_to_openai(body.get("tools"))
    
    thinking = _is_thinking(body)
    
    stream = bool(body.get("stream", False))

    if stream:
        return await _stream_messages(request, body, msgs, tools, thinking)

    # 非流式
    mid = _mid()
    ct = int(time.time())

    try:
        content, thinking_parts, tool_calls, usage_d, platform_id = await _collect_messages(
            body, msgs, tools, request.app[REGISTRY_KEY]
        )
    except NoCandidateError as exc:
        return _err(503, str(exc), "overloaded_error")
    except ProviderError as exc:
        return _err(502, str(exc), "api_error")
    except Exception as exc:
        logger.error("Anthropic messages 异常: %s", exc, exc_info=True)
        return _err(500, str(exc), "server_error")

    # 构建 Anthropic content blocks
    rc: List[Dict[str, Any]] = []
    if thinking_parts:
        rc.append({"type": "thinking", "thinking": "".join(thinking_parts)})
    if content:
        rc.append({"type": "text", "text": content})
    for tc in tool_calls:
        rc.append(_openai_tc_to_anth(tc))

    # 若无任何内容，补充空文本块（避免 content 为空列表）
    if not rc:
        rc.append({"type": "text", "text": ""})

    pt = sum(len(str(m.get("content", ""))) // 3 for m in msgs)
    ou: int
    if usage_d:
        ou = int(
            usage_d.get("completion_tokens")
            or usage_d.get("output_tokens")
            or (len(content) // 3 if content else 0)
        )
    else:
        ou = len(content) // 3 if content else 0

    resp = _json(
        {
            "id": mid,
            "type": "message",
            "role": "assistant",
            "content": rc,
            "model": mdl,
            "stop_reason": "tool_use" if tool_calls else "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": pt, "output_tokens": ou},
        }
    )
    if platform_id:
        resp._platform = platform_id
    return resp


async def list_models(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """模型列表端点 GET /anthropic/v1/models（Anthropic 格式）。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    registry = request.app[REGISTRY_KEY]
    ct = int(time.time())
    models: List[Dict[str, Any]] = []

    try:
        if hasattr(registry, "list_models"):
            raw = await registry.list_models()
            for m in raw:
                model_id = m if isinstance(m, str) else m.get("id", "")
                if model_id:
                    models.append(
                        {
                            "type": "model",
                            "id": model_id,
                            "display_name": model_id,
                            "created_at": ct,
                        }
                    )
    except Exception as exc:
        logger.warning("获取模型列表失败: %s", exc)

    return _json(
        {
            "type": "list",
            "data": models,
            "has_more": False,
            "first_id": models[0]["id"] if models else None,
            "last_id": models[-1]["id"] if models else None,
        }
    )


async def retrieve_model(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """模型详情端点 GET /anthropic/v1/models/{model_id}（Anthropic 格式）。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    model_id = request.match_info["model_id"]
    return _json(
        {
            "type": "model",
            "id": model_id,
            "display_name": model_id,
            "created_at": int(time.time()),
        }
    )


async def count_tokens(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """Token 计数端点 POST /v1/messages/count_tokens。

    估算请求的 token 数量（基于字符数 / 3 的简化估算）。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    body = await _get_json(request)
    if body is None:
        return _err(400, "Invalid JSON", "invalid_request_error")

    system_str = _normalize_anth_content(body.get("system"))
    msgs = _anth_messages_to_openai(
        body.get("messages", []), system_str
    )
    estimated = sum(
        len(str(m.get("content", ""))) // 3 for m in msgs
    )
    # 工具定义也计入 token
    tools = body.get("tools", [])
    for t in tools:
        estimated += len(json.dumps(t, ensure_ascii=False)) // 3

    return _json({"input_tokens": estimated})


# ═══════════════════════════════════════════════════════════════════════════
# 路由注册
# ═══════════════════════════════════════════════════════════════════════════


def setup_routes(app: aiohttp.web.Application) -> None:
    """注册所有 Anthropic 兼容路由。

    覆盖路由：
    - POST /v1/messages（带版本前缀）
    - POST /messages（无版本前缀，兼容旧客户端）
    - GET  /anthropic/v1/models（避免与 OpenAI /v1/models 冲突）
    - GET  /anthropic/v1/models/{model_id}
    - POST /v1/messages/count_tokens

    Args:
        app: aiohttp.web.Application 实例。
    """
    # Messages（核心端点，双路径）
    app.router.add_post("/v1/messages", messages_handler)
    app.router.add_post("/messages", messages_handler)

    # Token 计数
    app.router.add_post(
        "/v1/messages/count_tokens", count_tokens
    )

    # Models（使用 Anthropic 专属前缀，避免与 OpenAI /v1/models 冲突）
    app.router.add_get("/anthropic/v1/models", list_models)
    app.router.add_get("/anthropic/v1/models/{model_id}", retrieve_model)
