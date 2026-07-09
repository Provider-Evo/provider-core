# -*- coding: utf-8 -*-
from __future__ import annotations

"""OpenAI 兼容路由——共享工具函数与常量"""

import binascii
import uuid
from typing import Any, Dict, List, Optional, Union

import aiohttp.web

from src.core.server import json_response
from src.core.tools import normalize_content
from src.logger import get_logger

__all__ = [
    "_FNCALL_START",
    "_FNCALL_END",
    "_FNCALL_OPEN_TAG",
    "_FNCALL_CLOSE_TAG",
    "_id",
    "_cid",
    "_bid",
    "_fid",
    "_aid",
    "_tid",
    "_rid",
    "_vid",
    "_uid",
    "_json",
    "_err",
    "_not_supported",
    "_normalize_messages",
    "_extract_upload_files",
    "_mime_to_ext",
    "_sl",
]

logger = get_logger(__name__)

# fncall 标签
_FNCALL_START = "<function="
_FNCALL_END = "</" + "function>"
_FNCALL_OPEN_TAG = "<function_calls>"
_FNCALL_CLOSE_TAG = "</function_calls>"

# ═══════════════════════════════════════════════════════════════


# ════════════════════════════════════════════════════════════════
# 工具函数
# ════════════════════════════════════════════════════════════════


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
