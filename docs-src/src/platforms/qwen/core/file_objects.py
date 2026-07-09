from __future__ import annotations

# Qwen file object handling (re-exports from files.py)

from src.platforms.qwen.core.files import (
    build_file_object,
    build_url_file_object,
    _infer_content_type,
    _infer_filename,
    _get_type_attributes,
)

__all__ = [
    "build_file_object",
    "build_url_file_object",
]
