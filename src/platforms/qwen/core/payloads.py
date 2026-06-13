"""Qwen HTTP 请求体构建工具。

包括聊天补全、i2v 视频、停止、创建对话、TTS、替换内容等接口的载荷。
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from .endpoints import API_VERSION, USE_LOCAL_MODE
from .files import build_url_file_object


# ---------------------------------------------------------------------------
# 历史消息提取
# ---------------------------------------------------------------------------
def _collect_user_content(
    messages: List[Dict[str, Any]],
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """从历史消息中提取所有 user 文本与附件 URL 文件对象。

    Args:
        messages: OpenAI 格式消息列表。

    Returns:
        ``(text_parts, extra_files)``。
    """
    text_parts: List[str] = []
    extra_files: List[Dict[str, Any]] = []
    for msg in messages:
        if msg.get("role") != "user":
            continue
        _collect_one_message(
            msg.get("content", ""), text_parts, extra_files
        )
    return text_parts, extra_files


def _collect_one_message(
    msg_content: Any,
    text_parts: List[str],
    extra_files: List[Dict[str, Any]],
) -> None:
    """处理单条消息内容，将文本追加到 ``text_parts``、文件追加到 ``extra_files``。"""
    if isinstance(msg_content, str):
        text_parts.append(msg_content)
        return
    if not isinstance(msg_content, list):
        return
    for part in msg_content:
        if not isinstance(part, dict):
            continue
        _collect_one_part(part, text_parts, extra_files)


def _collect_one_part(
    part: Dict[str, Any],
    text_parts: List[str],
    extra_files: List[Dict[str, Any]],
) -> None:
    """处理单个 OpenAI content 片段。"""
    part_type = part.get("type", "")
    if part_type == "text":
        text_parts.append(part.get("text", ""))
        return
    if part_type == "image_url":
        url = _extract_url(part.get("image_url"))
        if url and not url.startswith("data:"):
            extra_files.append(build_url_file_object(url, "image"))
        return
    if part_type == "video_url":
        url = _extract_url(part.get("video_url"))
        if url and not url.startswith("data:"):
            extra_files.append(build_url_file_object(url, "video"))
        return
    if part_type == "input_audio":
        audio_obj = part.get("input_audio") or {}
        url = audio_obj.get("url", "") if isinstance(audio_obj, dict) else ""
        if url and not url.startswith("data:"):
            extra_files.append(build_url_file_object(url, "audio"))


def _extract_url(url_obj: Any) -> str:
    """从 OpenAI ``{"url": "..."}`` 形式或字符串中提取 URL。"""
    if isinstance(url_obj, dict):
        return url_obj.get("url", "") or ""
    if isinstance(url_obj, str):
        return url_obj
    return ""


# ---------------------------------------------------------------------------
# 聊天补全载荷
# ---------------------------------------------------------------------------
def build_payload(
    messages: List[Dict[str, Any]],
    model: str,
    chat_id: str,
    *,
    files: Optional[List[Dict[str, Any]]] = None,
    chat_type: str = "t2t",
    sub_chat_type: Optional[str] = None,
    parent_id: Optional[str] = None,
    thinking_enabled: bool = True,
    auto_thinking: bool = True,
    thinking_mode: str = "Auto",
    thinking_format: str = "summary",
    auto_search: bool = False,
    stream: bool = True,
) -> Dict[str, Any]:
    """构建聊天补全请求载荷。

    Args:
        messages: OpenAI 格式消息列表。
        model: 模型名称。
        chat_id: 对话 ID。
        files: 已上传到 OSS 的文件对象列表。
        chat_type: 聊天类型（``t2t`` / ``t2i`` / ``i2v``）。
        sub_chat_type: 子聊天类型；``None`` 时与 ``chat_type`` 相同。
        parent_id: 父消息 ID。
        thinking_enabled: 是否启用思考。
        auto_thinking: 是否自动思考。
        thinking_mode: 思考模式名称。
        thinking_format: 思考格式。
        auto_search: 是否自动搜索。
        stream: 是否流式。

    Returns:
        完整请求载荷字典。
    """
    if sub_chat_type is None:
        sub_chat_type = chat_type
    text_parts, extra_files = _collect_user_content(messages)
    content = "\n".join(filter(None, text_parts))
    all_files = list(files or []) + extra_files

    feature_config = _build_feature_config(
        thinking_enabled=thinking_enabled,
        auto_thinking=auto_thinking,
        thinking_mode=thinking_mode,
        thinking_format=thinking_format,
        auto_search=auto_search,
    )
    msg_ts = int(time.time())
    message_obj = _build_user_message(
        content=content,
        files=all_files,
        model=model,
        chat_type=chat_type,
        sub_chat_type=sub_chat_type,
        parent_id=parent_id,
        feature_config=feature_config,
        timestamp=msg_ts,
    )
    return _build_envelope(
        stream=stream,
        chat_id=chat_id,
        model=model,
        parent_id=parent_id,
        messages=[message_obj],
        timestamp=msg_ts + 1,
    )


def _build_feature_config(
    *,
    thinking_enabled: bool,
    auto_thinking: bool,
    thinking_mode: str,
    thinking_format: str,
    auto_search: bool,
) -> Dict[str, Any]:
    """构造 ``feature_config`` 字典。"""
    cfg: Dict[str, Any] = {
        "thinking_enabled": thinking_enabled,
        "output_schema": "phase",
        "research_mode": "normal",
        "auto_thinking": auto_thinking,
        "thinking_mode": thinking_mode,
        "auto_search": auto_search,
    }
    if thinking_enabled:
        cfg["thinking_format"] = thinking_format
    return cfg


def _build_user_message(
    *,
    content: str,
    files: List[Dict[str, Any]],
    model: str,
    chat_type: str,
    sub_chat_type: str,
    parent_id: Optional[str],
    feature_config: Dict[str, Any],
    timestamp: int,
) -> Dict[str, Any]:
    """构造单条 user 消息对象。"""
    return {
        "fid": str(uuid.uuid4()),
        "parentId": parent_id,
        "childrenIds": [str(uuid.uuid4())],
        "role": "user",
        "content": content,
        "user_action": "chat",
        "files": files,
        "timestamp": timestamp,
        "models": [model],
        "chat_type": chat_type,
        "feature_config": feature_config,
        "extra": {"meta": {"subChatType": sub_chat_type}},
        "sub_chat_type": sub_chat_type,
        "parent_id": parent_id,
    }


def _build_envelope(
    *,
    stream: bool,
    chat_id: str,
    model: str,
    parent_id: Optional[str],
    messages: List[Dict[str, Any]],
    timestamp: int,
) -> Dict[str, Any]:
    """构造请求顶层信封。"""
    return {
        "stream": stream,
        "version": API_VERSION,
        "incremental_output": True,
        "chat_id": chat_id,
        "chat_mode": "local" if USE_LOCAL_MODE else "normal",
        "model": model,
        "parent_id": parent_id,
        "messages": messages,
        "timestamp": timestamp,
    }


# ---------------------------------------------------------------------------
# i2v 视频载荷
# ---------------------------------------------------------------------------
def build_i2v_payload(
    prompt: str,
    chat_id: str,
    model: str,
    image_url: str,
    image_name: str,
    size: str,
    parent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """构建图片到视频（i2v）专用请求载荷。

    Args:
        prompt: 视频生成描述。
        chat_id: 对话 ID。
        model: 模型名称。
        image_url: 参考图片 URL（已上传到 OSS）。
        image_name: 图片文件名。
        size: 视频尺寸（``16:9`` / ``9:16`` / ``1:1``）。
        parent_id: 父消息 ID。

    Returns:
        i2v 请求载荷字典。
    """
    msg_ts = int(time.time())
    file_obj = _build_i2v_file(image_url, image_name)
    message_obj = {
        "fid": str(uuid.uuid4()),
        "parentId": parent_id,
        "childrenIds": [str(uuid.uuid4())],
        "role": "user",
        "content": prompt,
        "user_action": "chat",
        "files": [file_obj],
        "timestamp": msg_ts,
        "models": [model],
        "chat_type": "i2v",
        "feature_config": {
            "thinking_enabled": True,
            "output_schema": "phase",
            "research_mode": "normal",
            "auto_thinking": False,
            "thinking_mode": "Thinking",
        },
        "extra": {"meta": {"subChatType": "i2v", "size": size}},
        "sub_chat_type": "i2v",
        "parent_id": parent_id,
    }
    envelope = _build_envelope(
        stream=False,
        chat_id=chat_id,
        model=model,
        parent_id=parent_id,
        messages=[message_obj],
        timestamp=msg_ts,
    )
    envelope["chat_mode"] = "normal"
    envelope["size"] = size
    return envelope


def _build_i2v_file(image_url: str, image_name: str) -> Dict[str, Any]:
    """构造 i2v 引用的参考图文件对象。"""
    return {
        "type": "image",
        "name": image_name,
        "file_type": "image/png",
        "showType": "image",
        "file_class": "vision",
        "url": image_url,
        "isQuote": True,
    }


# ---------------------------------------------------------------------------
# 其他载荷
# ---------------------------------------------------------------------------
def build_stop_payload(chat_id: str) -> Dict[str, Any]:
    """构建停止生成请求载荷。

    Args:
        chat_id: 需要停止生成的对话 ID。

    Returns:
        停止生成请求载荷字典。
    """
    return {"chat_id": chat_id}


def build_new_chat_payload(
    model: str,
    chat_type: str = "t2t",
) -> Dict[str, Any]:
    """构建创建新对话的请求载荷。

    Args:
        model: 模型名称。
        chat_type: 聊天类型。

    Returns:
        创建对话请求载荷。
    """
    return {
        "title": "新建对话",
        "models": [model],
        "chat_mode": "local" if USE_LOCAL_MODE else "normal",
        "chat_type": chat_type,
        "timestamp": int(time.time() * 1000),
    }


def build_tts_payload(
    chat_id: str,
    response_id: str,
) -> Dict[str, Any]:
    """构建 TTS 语音合成请求载荷。

    Args:
        chat_id: 对话 ID。
        response_id: 助手消息 ID（``response_id``）。

    Returns:
        TTS 请求载荷字典。
    """
    return {
        "chat_id": chat_id,
        "timestamp": int(time.time()),
        "messages": [
            {
                "id": response_id,
                "role": "assistant",
                "sub_chat_type": "tts",
            }
        ],
    }


def build_replace_content_payload(
    new_content: str,
    origin_content: str,
) -> Dict[str, Any]:
    """构建替换消息内容的请求载荷。

    TTS 流程需要先将助手消息内容替换为目标文本，再请求 TTS 合成。

    Args:
        new_content: 新的消息内容（目标 TTS 文本）。
        origin_content: 原始消息内容（用于 token 估算）。

    Returns:
        替换内容请求载荷字典。
    """
    return {
        "content_list": [
            {
                "content": new_content,
                "phase": "answer",
                "status": "finished",
                "extra": None,
                "role": "assistant",
                "usage": _estimate_replace_usage(
                    new_content, origin_content
                ),
            }
        ]
    }


def _estimate_replace_usage(
    new_content: str, origin_content: str
) -> Dict[str, Any]:
    """估算替换消息的 token 用量字段。"""
    return {
        "input_tokens": max(1, len(origin_content) // 3),
        "output_tokens": max(1, len(new_content) // 3),
        "total_tokens": max(
            1, (len(origin_content) + len(new_content)) // 3
        ),
        "prompt_tokens_details": {"cached_tokens": 0},
    }
