from __future__ import annotations

"""openaifm TTS 相关定义。"""

from typing import Dict, List

import aiohttp

from .constants import (
    DEFAULT_STYLE,
    DEFAULT_VOICE,
    STYLES,
    STYLE_PROMPTS,
    VOICES,
)

__all__ = [
    "DEFAULT_STYLE",
    "DEFAULT_VOICE",
    "STYLES",
    "STYLE_PROMPTS",
    "VOICES",
    "build_tts_form_data",
]


def build_tts_form_data(
    text: str,
    prompt: str,
    voice: str,
    vibe: str = "",
) -> aiohttp.FormData:
    """构建 TTS multipart 表单数据。

    Args:
        text: 合成文本（API 字段名: input）。
        prompt: 风格提示（API 字段名: prompt）。
        voice: 声音名称。
        vibe: 氛围参数（可选）。

    Returns:
        aiohttp.FormData 实例（multipart/form-data）。
    """
    form = aiohttp.FormData()
    form.add_field("input", text)
    form.add_field("prompt", prompt or "")
    form.add_field("voice", voice or DEFAULT_VOICE)
    form.add_field("vibe", vibe or "")
    return form
