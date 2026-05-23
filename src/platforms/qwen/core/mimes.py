"""文件 MIME 类型映射与分类工具。

纯函数模块：仅按文件名/Content-Type 推断分类，不做任何 I/O。
"""

from __future__ import annotations

import os
from typing import Dict, Final, Tuple

FILE_TYPE_MAPPING: Final[Dict[str, str]] = {
    "image/jpeg": "image",
    "image/jpg": "image",
    "image/png": "image",
    "image/gif": "image",
    "image/webp": "image",
    "image/bmp": "image",
    "video/mp4": "video",
    "video/avi": "video",
    "video/mov": "video",
    "video/quicktime": "video",
    "audio/mpeg": "audio",
    "audio/mp3": "audio",
    "audio/wav": "audio",
    "audio/x-wav": "audio",
    "audio/aac": "audio",
    "audio/ogg": "audio",
    "audio/m4a": "audio",
    "audio/opus": "audio",
    "application/pdf": "file",
    "text/plain": "file",
    "text/csv": "file",
    "application/json": "file",
}

EXTENSION_TO_MIME: Final[Dict[str, str]] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".mp4": "video/mp4",
    ".avi": "video/avi",
    ".mov": "video/quicktime",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
    ".m4a": "audio/m4a",
    ".opus": "audio/opus",
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".json": "application/json",
    ".md": "text/markdown",
    ".yaml": "text/yaml",
    ".py": "text/x-python",
}

# data: URI 的 MIME -> 默认扩展名
DATA_URI_EXT_MAP: Final[Dict[str, str]] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "video/mp4": ".mp4",
    "application/pdf": ".pdf",
}


def get_mime_type(filename: str) -> str:
    """根据文件名推断 MIME 类型。

    Args:
        filename: 文件名（含扩展名）。

    Returns:
        MIME 类型字符串；无法推断时返回 ``application/octet-stream``。

    Examples:
        >>> get_mime_type("a.PNG")
        'image/png'
        >>> get_mime_type("unknown.xyz")
        'application/octet-stream'
    """
    ext = os.path.splitext(filename)[1].lower()
    return EXTENSION_TO_MIME.get(ext, "application/octet-stream")


def get_file_category(content_type: str) -> Tuple[str, str]:
    """获取文件分类（``file_type`` 与 ``file_class``）。

    Args:
        content_type: MIME 类型。

    Returns:
        ``(file_type, file_class)`` 元组。

    Examples:
        >>> get_file_category("image/png")
        ('image', 'vision')
        >>> get_file_category("audio/mpeg")
        ('audio', 'audio')
    """
    file_type = FILE_TYPE_MAPPING.get(content_type, "file")
    if content_type.startswith("image/"):
        file_class = "vision"
    elif content_type.startswith("video/"):
        file_class = "vision"
    elif content_type.startswith("audio/"):
        file_class = "audio"
    else:
        file_class = "document"
    return file_type, file_class
