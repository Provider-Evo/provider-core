from __future__ import annotations

"""Anthropic 请求/响应格式转换与 dispatch 参数构建。"""

from src.routes.anthropic.convert.format_convert import (
    _anth_content_to_openai,
    _anth_messages_to_openai,
    _anth_tools_to_openai,
    _build_dispatch_kwargs,
    _content_block_to_text,
    _extract_image_source,
    _is_thinking,
    _mid,
    _normalize_anth_content,
    _openai_tc_to_anth,
    _tc_id,
)
from src.routes.anthropic.convert.http_utils import _err, _json

__all__ = [
    "_anth_content_to_openai",
    "_anth_messages_to_openai",
    "_anth_tools_to_openai",
    "_build_dispatch_kwargs",
    "_content_block_to_text",
    "_err",
    "_extract_image_source",
    "_is_thinking",
    "_json",
    "_mid",
    "_normalize_anth_content",
    "_openai_tc_to_anth",
    "_tc_id",
]
