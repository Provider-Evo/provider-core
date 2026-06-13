"""SSE 单行解析（无状态）。

提供两层 API：

- :func:`parse_sse_event` -- 结构化解析，区分 ``answer`` /
  ``thinking_summary`` / ``image_gen_tool`` / ``image_gen`` /
  ``video_gen`` / ``usage`` / ``response_created`` / ``error`` / ``other``。
- :func:`parse_sse_line` -- 进一步映射为公开协议（``str`` 文本增量 /
  ``{"thinking": ...}`` / ``{"usage": ...}`` / ``None``）。

所有状态化逻辑（如 ``thinking_summary`` 增量累积）由调用方
:mod:`.stream` 维护。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Union


def parse_sse_event(data_str: str) -> Optional[Dict[str, Any]]:
    """解析单行 SSE ``data`` 字段为结构化事件字典。

    Args:
        data_str: 已去除 ``data:`` 前缀与空白的字符串。

    Returns:
        结构化事件字典；不可识别 / 空 / ``[DONE]`` 时返回 ``None``。

    返回字典的 ``type`` 字段枚举：

    - ``"answer"``：正文内容增量
    - ``"thinking_summary"``：思考摘要（含 ``status`` / ``extra``）
    - ``"image_gen_tool"``：图片生成工具结果（含 ``urls`` 列表）
    - ``"image_gen"``：直接图片内容（含 ``content`` URL）
    - ``"video_gen"``：视频生成结果（含 ``content`` URL）
    - ``"usage"``：token 用量
    - ``"response_created"``：响应创建事件（含 ``response_id``）
    - ``"error"``：服务器错误
    - ``"other"``：其他未知 ``phase`` 内容
    """
    data = _safe_loads(data_str)
    if data is None:
        return None
    head = _parse_head_event(data)
    if head is not None:
        return head
    return _parse_choice_event(data)


def _safe_loads(data_str: str) -> Optional[Any]:
    """安全 JSON 解析；空 / ``[DONE]`` / 非法 JSON 一律返回 ``None``。"""
    if not data_str or data_str == "[DONE]":
        return None
    try:
        return json.loads(data_str)
    except (json.JSONDecodeError, ValueError):
        return None


def _parse_head_event(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """解析顶层非 choices 事件：``error`` / ``response.created``。"""
    if "error" in data:
        return {"type": "error", "message": str(data["error"])}
    if "response.created" in data:
        created = data["response.created"]
        return {
            "type": "response_created",
            "response_id": created.get("response_id", ""),
        }
    return None


def _parse_choice_event(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """解析 ``choices[0].delta`` 流式增量；也兼容仅含 ``usage`` 的事件。"""
    usage = data.get("usage")
    choices = data.get("choices", [])
    if not choices:
        return {"type": "usage", "data": usage} if usage else None

    delta = choices[0].get("delta", {})
    result = _dispatch_phase(delta)

    if usage:
        if result is None:
            return {"type": "usage", "data": usage}
        result["usage"] = usage
    return result


def _dispatch_phase(delta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """按 ``delta.phase`` 派发到对应的事件构造器。"""
    phase = delta.get("phase")
    if phase == "answer":
        return _build_answer(delta)
    if phase == "thinking_summary":
        return _build_thinking(delta)
    if phase == "image_gen_tool":
        return _build_image_tool(delta)
    if phase == "image_gen":
        return _build_image_gen(delta)
    if phase == "video_gen":
        return _build_video_gen(delta)
    return _build_other(delta)


def _build_answer(delta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """构造 ``answer`` 事件。"""
    content = delta.get("content")
    if content and delta.get("status") != "finished":
        return {"type": "answer", "content": content}
    return None


def _build_thinking(delta: Dict[str, Any]) -> Dict[str, Any]:
    """构造 ``thinking_summary`` 事件。"""
    return {
        "type": "thinking_summary",
        "status": delta.get("status") or "",
        "extra": delta.get("extra", {}),
    }


def _build_image_tool(delta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """构造 ``image_gen_tool`` 事件（仅当函数角色 + 已 finish）。"""
    if delta.get("role") != "function" or delta.get("status") != "finished":
        return None
    extra = delta.get("extra", {})
    imgs = extra.get("image_list", extra.get("tool_result", []))
    urls = [
        img.get("image", "")
        for img in imgs
        if isinstance(img, dict) and img.get("image")
    ]
    if not urls:
        return None
    return {"type": "image_gen_tool", "urls": urls}


def _build_image_gen(delta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """构造 ``image_gen`` 直接图片事件。"""
    content = delta.get("content")
    if not content:
        return None
    return {
        "type": "image_gen",
        "content": content,
        "extra": delta.get("extra", {}),
    }


def _build_video_gen(delta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """构造 ``video_gen`` 事件。"""
    content = delta.get("content")
    if not content:
        return None
    return {"type": "video_gen", "content": content}


def _build_other(delta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """兜底：未知非空 ``phase`` 且有 ``content`` 时归为 ``other``。"""
    phase = delta.get("phase")
    content = delta.get("content")
    status = delta.get("status")
    if (
        phase is not None
        and phase != ""
        and content
        and status != "finished"
    ):
        return {"type": "other", "content": content}
    return None


def parse_sse_line(
    data_str: str,
) -> Optional[Union[str, Dict[str, Any]]]:
    """解析单行 SSE ``data`` 字段并映射为公开协议。

    Args:
        data_str: 已去除 ``data:`` 前缀的原始 SSE 数据行。

    Returns:
        - 文本增量 -> ``str``
        - 思考摘要 -> ``{"thinking": "..."}``
        - 用量信息 -> ``{"usage": {...}}``
        - 其他事件 / 跳过 -> ``None``
    """
    event = parse_sse_event(data_str)
    if event is None:
        return None
    evt_type = event.get("type", "")
    if evt_type == "answer":
        return event.get("content", "")
    if evt_type == "thinking_summary":
        return _thinking_to_text(event.get("extra", {}))
    if evt_type == "usage":
        return {"usage": event.get("data", {})}
    return None


def _thinking_to_text(extra: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """从 ``thinking_summary.extra`` 中拼装公开协议的 thinking 文本。"""
    if not extra:
        return None
    titles = extra.get("summary_title", {}).get("content", [])
    thoughts = extra.get("summary_thought", {}).get("content", [])
    parts: List[str] = []
    for title, thought in zip(titles, thoughts):
        if title or thought:
            parts.append(
                "{}: {}".format(title, thought)
                if title
                else str(thought)
            )
    if not parts:
        return None
    return {"thinking": "\n".join(parts)}
