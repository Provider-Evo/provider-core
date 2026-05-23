"""Qwen ``messages.files`` 字段的文件对象构建工具。

本模块只做数据封装，不发起任何网络请求或文件 I/O。
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Any, Dict, Tuple

from .mimes import FILE_TYPE_MAPPING


def build_file_object(
    file_id: str,
    file_url: str,
    filename: str,
    size: int,
    content_type: str,
    user_id: str,
) -> Dict[str, Any]:
    """构建已 OSS 上传后的文件对象。

    Args:
        file_id: 文件唯一 ID（建议传入 ``uuid.uuid4().hex``）。
        file_url: 文件 OSS URL。
        filename: 文件名。
        size: 文件大小（字节）。
        content_type: MIME 类型。
        user_id: 用户 ID。

    Returns:
        Qwen API 文件对象字典；可直接放入 ``messages[*].files``。
    """
    current_time = int(time.time() * 1000)
    item_id = str(uuid.uuid4())
    upload_task_id = str(uuid.uuid4())

    file_type = FILE_TYPE_MAPPING.get(content_type, "file")
    if content_type.startswith("image/"):
        file_class = "vision"
        show_type = "image"
    elif content_type.startswith("video/"):
        file_class = "vision"
        show_type = "video"
    elif content_type.startswith("audio/"):
        file_class = "audio"
        show_type = "audio"
    else:
        file_class = "document"
        show_type = "file"

    return {
        "type": file_type,
        "file": {
            "created_at": current_time,
            "data": {},
            "filename": filename,
            "hash": None,
            "id": file_id,
            "user_id": user_id,
            "meta": {
                "name": filename,
                "size": size,
                "content_type": content_type,
            },
            "update_at": current_time,
        },
        "id": file_id,
        "url": file_url,
        "name": filename,
        "collection_name": "",
        "progress": 0,
        "status": "uploaded",
        "greenNet": "success",
        "size": size,
        "error": "",
        "itemId": item_id,
        "file_type": content_type,
        "showType": show_type,
        "file_class": file_class,
        "uploadTaskId": upload_task_id,
    }


def _infer_content_type(file_url: str, file_type: str) -> str:
    """从 URL 或文件类型推断 MIME content type。"""
    if file_url.startswith("data:"):
        header = file_url.split(",")[0] if "," in file_url else ""
        mime = header.split(":")[1].split(";")[0] if ":" in header else ""
        if mime:
            return mime

    basename = os.path.basename(file_url.split("?")[0]).lower()
    ext_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mov": "video/quicktime",
        ".avi": "video/x-msvideo",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
        ".pdf": "application/pdf",
        ".txt": "text/plain",
    }
    for ext, ct in ext_map.items():
        if basename.endswith(ext):
            return ct

    defaults = {
        "image": "image/jpeg",
        "video": "video/mp4",
        "audio": "audio/mpeg",
        "document": "application/octet-stream",
    }
    return defaults.get(file_type, "application/octet-stream")


def _infer_filename(file_url: str, file_type: str) -> str:
    """从 URL 或文件类型推断文件名。"""
    basename = os.path.basename(file_url.split("?")[0])
    if basename:
        return basename
    defaults = {
        "image": "image.jpg",
        "video": "video.mp4",
        "audio": "audio.mp3",
        "document": "document.pdf",
    }
    return defaults.get(file_type, "file.bin")


def _get_type_attributes(file_type: str, is_base64: bool) -> Tuple[str, str]:
    """获取文件类型对应的 ``(showType, file_class)``。"""
    type_map = {
        "image": ("image", "vision" if not is_base64 else "upload"),
        "video": ("video", "vision"),
        "audio": ("audio", "vision"),
        "document": ("document", "upload"),
    }
    return type_map.get(file_type, ("file", "upload"))


def build_url_file_object(
    file_url: str,
    file_type: str = "image",
) -> Dict[str, Any]:
    """构建直接使用 URL 的文件对象（无需 OSS 上传）。

    用于处理 OpenAI vision 格式中的 ``image_url``、``video_url``、
    ``input_audio`` 字段。

    Args:
        file_url: 文件 URL 或 base64 ``data:`` URI。
        file_type: 文件类型（``"image"`` / ``"video"`` / ``"audio"`` /
            ``"document"``）。

    Returns:
        Qwen API 文件对象字典。
    """
    current_time = int(time.time() * 1000)
    file_id = str(uuid.uuid4())
    item_id = str(uuid.uuid4())
    upload_task_id = str(uuid.uuid4())

    is_base64 = file_url.startswith("data:")
    content_type = _infer_content_type(file_url, file_type)
    filename = _infer_filename(file_url, file_type)

    if not is_base64:
        filename = os.path.basename(file_url.split("?")[0]) or filename

    show_type, file_class = _get_type_attributes(file_type, is_base64)

    return {
        "type": file_type,
        "file": {
            "created_at": current_time,
            "data": {},
            "filename": filename,
            "hash": None,
            "id": file_id,
            "user_id": "",
            "meta": {
                "name": filename,
                "size": 0,
                "content_type": content_type,
            },
            "update_at": current_time,
        },
        "id": file_id,
        "url": file_url,
        "name": filename,
        "collection_name": "",
        "progress": 0,
        "status": "uploaded",
        "greenNet": "success",
        "size": 0,
        "error": "",
        "itemId": item_id,
        "file_type": content_type,
        "showType": show_type,
        "file_class": file_class,
        "uploadTaskId": upload_task_id,
    }
