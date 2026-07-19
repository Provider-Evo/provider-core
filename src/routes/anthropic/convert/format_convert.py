from __future__ import annotations

"""Anthropic 与 OpenAI 之间的内容/工具/参数格式转换。"""

import json
import uuid
from typing import Any, Dict, List, Optional, Union

from src.core.utils.compat.tools import normalize_content
from src.foundation.config.resolve import resolve_model

# ═══════════════════════════════════════════════════════════════════════════
# ID 生成工具
# ═══════════════════════════════════════════════════════════════════════════


def _mid() -> str:
    return "msg_{}".format(uuid.uuid4().hex[:24])


def _tc_id() -> str:
    return "toolu_{}".format(uuid.uuid4().hex[:24])


# ═══════════════════════════════════════════════════════════════════════════
# Anthropic → OpenAI 内容规范化与转换
# ═══════════════════════════════════════════════════════════════════════════


def _normalize_anth_content(content: Any) -> Optional[str]:
    """规范化 Anthropic system/content 字段为字符串。

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
        return _process_list_content(content)
    result = str(content)
    return result if result else None


def _process_list_content(content: List) -> Optional[str]:
    """处理 list 类型 content，提取文本列表并合并。

    Args:
        content: Anthropic content 列表。

    Returns:
        合并后的字符串，空列表时返回 None。
    """
    texts: List[str] = []
    for item in content:
        if isinstance(item, dict):
            _process_dict_item(item, texts)
        elif isinstance(item, str) and item:
            texts.append(item)
    return "\n".join(texts) if texts else None


def _process_dict_item(item: Dict[str, Any], texts: List[str]) -> None:
    """处理 dict 类型 item，提取文本添加到列表。

    Args:
        item: Anthropic content item 字典。
        texts: 文本列表（就地修改）。
    """
    item_type = item.get("type", "")
    if item_type == "text":
        text = item.get("text", "")
        if text:
            texts.append(text)
    elif "text" in item:
        text = item.get("text", "")
        if text:
            texts.append(text)


def _extract_image_source(image_block: Dict[str, Any]) -> str:
    """从 Anthropic image block 提取可读描述。"""
    source = image_block.get("source", {})
    source_type = source.get("type", "")
    if source_type == "url":
        return "[image: {}]".format(source.get("url", "unknown"))
    if source_type == "base64":
        media_type = source.get("media_type", "image")
        return "[image: base64 {} data]".format(media_type)
    return "[image]"


def _content_block_to_text(block: Dict[str, Any]) -> str:
    """将单个 Anthropic content block 转换为文本描述。"""
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
            json.dumps(inp, ensure_ascii=False) if isinstance(inp, dict) else str(inp)
        )
        return "Tool call ({}): {}({})".format(tool_id, name, inp_str)
    if btype == "thinking":
        return "[thinking: {}]".format(block.get("thinking", ""))
    return block.get("text", str(block))


def _image_block_to_openai(block: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """将 Anthropic image block 转换为 OpenAI image_url block。"""
    source = block.get("source", {})
    source_type = source.get("type", "")
    if source_type == "url":
        return {
            "type": "image_url",
            "image_url": {"url": source.get("url", "")},
        }
    if source_type == "base64":
        media_type = source.get("media_type", "image/jpeg")
        data = source.get("data", "")
        return {
            "type": "image_url",
            "image_url": {"url": "data:{};base64,{}".format(media_type, data)},
        }
    return None


def _multimodal_blocks_to_openai(content: List) -> List[Dict[str, Any]]:
    """将包含 image block 的 Anthropic content 列表转换为 OpenAI 多模态 blocks。"""
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
            image_block = _image_block_to_openai(block)
            if image_block is not None:
                result_blocks.append(image_block)
        else:
            text = _content_block_to_text(block)
            if text:
                result_blocks.append({"type": "text", "text": text})

    return result_blocks


def _anth_content_to_openai(
    content: Any,
) -> Union[str, List[Dict[str, Any]]]:
    """将 Anthropic content 转换为 OpenAI content 格式。

    支持视觉多模态：image block 转换为 OpenAI image_url 格式。
    """
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content)

    has_image = any(isinstance(b, dict) and b.get("type") == "image" for b in content)

    if not has_image:
        parts: List[str] = []
        for block in content:
            if isinstance(block, dict):
                parts.append(_content_block_to_text(block))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(filter(None, parts))

    result_blocks = _multimodal_blocks_to_openai(content)
    return result_blocks if result_blocks else ""


def _anth_messages_to_openai(
    messages: List[Dict[str, Any]],
    system: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """将 Anthropic 格式 messages 转换为 OpenAI 格式。"""
    out: List[Dict[str, Any]] = []
    if system:
        out.append({"role": "system", "content": system})

    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        converted = _anth_content_to_openai(content)
        out.append({"role": role, "content": converted})

    if not out:
        out.append({"role": "user", "content": ""})

    return out


def _anth_tools_to_openai(
    tools: Optional[List[Dict[str, Any]]],
) -> Optional[List[Dict[str, Any]]]:
    """将 Anthropic 格式工具转换为 OpenAI 格式。"""
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
    """判断请求是否开启 thinking 模式。"""
    t = body.get("thinking")
    if t is None:
        return False
    if isinstance(t, bool):
        return t
    if isinstance(t, dict):
        return t.get("type") == "enabled" or bool(t.get("enabled", False))
    return bool(t)


# ═══════════════════════════════════════════════════════════════════════════
# OpenAI tool_call → Anthropic tool_use / dispatch kwargs 构建
# ═══════════════════════════════════════════════════════════════════════════


def _openai_tc_to_anth(
    tc: Dict[str, Any],
) -> Dict[str, Any]:
    """将 OpenAI tool_call 转换为 Anthropic tool_use content block。

    id 必须以 toolu_ 开头；若上游 id 不符合，生成新的合规 id。
    """
    func = tc.get("function", {})
    args_raw = func.get("arguments", "{}")
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
    """构建 gateway.dispatch 调用参数。"""
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
