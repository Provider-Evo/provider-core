from __future__ import annotations

"""Anthropic 请求/响应格式转换与 dispatch 参数构建。"""

import json
import uuid
from typing import Any, Dict, List, Optional, Union

import aiohttp.web
from src.core.config.resolver import resolve_model
from src.core.server import json_response
from src.core.utils.compat.tools import normalize_content

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
