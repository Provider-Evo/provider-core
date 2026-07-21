"""Anthropic 路由处理器与非流式消息收集。"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, Tuple

import aiohttp.web

from src.core.server import (
    REGISTRY_KEY,
)
from src.core.server import clean_fncall as _clean_fncall
from src.core.server import get_json as _get_json
from src.core.utils.compat.tools import parse_fncall_xml
from src.core.utils.errors import NoCandidateError, ProviderError
from src.foundation.config.resolve import resolve_model
from src.foundation.logger import get_logger
from src.routes.anthropic.convert import (
    _anth_messages_to_openai,
    _anth_tools_to_openai,
    _build_dispatch_kwargs,
    _err,
    _is_thinking,
    _json,
    _mid,
    _normalize_anth_content,
    _openai_tc_to_anth,
)
from src.routes.anthropic.streaming.stream import _stream_messages

from src.routes.shared.thinking import resolve_include_thinking_in_history

logger = get_logger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# 非流式内容收集
# ═══════════════════════════════════════════════════════════════════════════


def _collect_dispatch_dict_chunk(
    ch: Dict[str, Any],
    thinking_parts: List[str],
    tool_calls: List[Dict[str, Any]],
    usage_d: Optional[Dict[str, Any]],
    platform_id: str,
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]], str]:
    if "_meta" in ch:
        return tool_calls, usage_d, ch["_meta"].get("platform", "")
    if "thinking" in ch:
        thinking_parts.append(ch["thinking"])
    elif "tool_calls" in ch:
        tool_calls = ch["tool_calls"]
    elif "usage" in ch:
        usage_d = ch["usage"]
    return tool_calls, usage_d, platform_id


async def _consume_dispatch_chunks(
    body: Dict[str, Any],
    msgs: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]],
    registry: Any,
) -> Tuple[List[str], List[str], List[Dict[str, Any]], Optional[Dict[str, Any]], str]:
    """消费 gateway.dispatch 的输出，按 chunk 类型分类收集。"""
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
            continue
        if isinstance(ch, dict):
            tool_calls, usage_d, platform_id = _collect_dispatch_dict_chunk(
                ch,
                thinking_parts,
                tool_calls,
                usage_d,
                platform_id,
            )

    return content_parts, thinking_parts, tool_calls, usage_d, platform_id


def _resolve_fncall_tool_calls(
    raw_content: str,
    cleaned: str,
    tool_calls: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]],
    platform_id: str,
) -> Tuple[str, List[Dict[str, Any]]]:
    """在没有结构化 tool_calls 时，尝试从文本中解析 fncall 标签。"""
    if tool_calls:
        return "", tool_calls

    from src.core.fncall.reg import get_protocol

    proto = get_protocol(platform_id=platform_id)
    trigger_tags = proto.get_trigger_tags()
    has_trigger = any(tag in raw_content for tag in trigger_tags)
    if has_trigger:
        # 文本中含有 fncall 标签，尝试解析
        parsed = parse_fncall_xml(raw_content, tools)
        if parsed:
            return "", parsed

    return cleaned, tool_calls


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
    content_parts, thinking_parts, tool_calls, usage_d, platform_id = (
        await _consume_dispatch_chunks(body, msgs, tools, registry)
    )

    # 清理文本中残留的 fncall 标签
    raw_content = "".join(content_parts)
    cleaned = _clean_fncall(raw_content, platform_id=platform_id)

    cleaned, tool_calls = _resolve_fncall_tool_calls(
        raw_content,
        cleaned,
        tool_calls,
        tools,
        platform_id,
    )

    return cleaned, thinking_parts, tool_calls, usage_d, platform_id


# ═══════════════════════════════════════════════════════════════════════════
# 路由处理器
# ═══════════════════════════════════════════════════════════════════════════


def _build_anthropic_content_blocks(
    content: str,
    thinking_parts: List[str],
    tool_calls: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """构建 Anthropic content blocks 列表。"""
    blocks: List[Dict[str, Any]] = []
    if thinking_parts:
        blocks.append({"type": "thinking", "thinking": "".join(thinking_parts)})
    if content:
        blocks.append({"type": "text", "text": content})
    for tc in tool_calls:
        blocks.append(_openai_tc_to_anth(tc))
    if not blocks:
        blocks.append({"type": "text", "text": ""})
    return blocks


def _anthropic_usage(
    msgs: List[Dict], content: str, usage_d: Optional[Dict]
) -> tuple[int, int]:
    """计算 Anthropic usage 的 input/output tokens。"""
    pt = sum(len(str(m.get("content", ""))) // 3 for m in msgs)
    if usage_d:
        ou = int(
            usage_d.get("completion_tokens")
            or usage_d.get("output_tokens")
            or (len(content) // 3 if content else 0)
        )
    else:
        ou = len(content) // 3 if content else 0
    return pt, ou


def _parse_messages_request(
    body: Dict[str, Any]
) -> tuple[str | None, aiohttp.web.StreamResponse | None]:
    """校验 messages 请求体；失败返回 (None, error_response)。"""
    messages_raw = body.get("messages", [])
    if not messages_raw:
        return None, _err(400, "messages is required", "invalid_request_error")
    mdl = body.get("model", "")
    if not mdl:
        return None, _err(400, "model is required", "invalid_request_error")
    return resolve_model(mdl, "anthropic"), None


def _messages_collect_error(exc: Exception) -> aiohttp.web.StreamResponse:
    if isinstance(exc, NoCandidateError):
        return _err(503, str(exc), "overloaded_error")
    if isinstance(exc, ProviderError):
        return _err(502, str(exc), "api_error")
    from src.core.utils.errors.biz import NetworkError

    if isinstance(exc, aiohttp.ClientConnectorError):
        err = NetworkError(f"连接失败: {exc}", original=exc)
        logger.error("Anthropic 连接错误: %s", exc, exc_info=True)
    else:
        err = exc
        logger.error("Anthropic messages 异常: %s", exc, exc_info=True)
    return _err(500, str(err), "server_error")


async def messages_handler(
    request: aiohttp.web.Request,
) -> aiohttp.web.StreamResponse:
    """Anthropic Messages 端点处理器 POST /v1/messages & POST /messages。"""
    body = await _get_json(request)
    if body is None:
        return _err(400, "Invalid JSON in request body", "invalid_request_error")
    mdl, err = _parse_messages_request(body)
    if err is not None:
        return err
    system_str = _normalize_anth_content(body.get("system"))
    thinking = _is_thinking(body)
    include_thinking = resolve_include_thinking_in_history(
        body, thinking_enabled=thinking
    )
    msgs = _anth_messages_to_openai(
        body.get("messages", []),
        system_str,
        include_thinking_in_history=include_thinking,
    )
    tools = _anth_tools_to_openai(body.get("tools"))
    if bool(body.get("stream", False)):
        return await _stream_messages(request, body, msgs, tools, thinking)
    try:
        content, thinking_parts, tool_calls, usage_d, platform_id = (
            await _collect_messages(body, msgs, tools, request.app[REGISTRY_KEY])
        )
    except Exception as exc:
        return _messages_collect_error(exc)
    rc = _build_anthropic_content_blocks(content, thinking_parts, tool_calls)
    pt, ou = _anthropic_usage(msgs, content, usage_d)
    resp = _json(
        {
            "id": _mid(),
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
    thinking = _is_thinking(body)
    include_thinking = resolve_include_thinking_in_history(
        body, thinking_enabled=thinking
    )
    msgs = _anth_messages_to_openai(
        body.get("messages", []),
        system_str,
        include_thinking_in_history=include_thinking,
    )
    estimated = sum(len(str(m.get("content", ""))) // 3 for m in msgs)
    # 工具定义也计入 token
    tools = body.get("tools", [])
    for t in tools:
        estimated += len(json.dumps(t, ensure_ascii=False)) // 3

    return _json({"input_tokens": estimated})
