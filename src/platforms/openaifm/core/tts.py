from __future__ import annotations

"""openaifm TTS 相关定义。"""

from typing import Dict, List

from .consts import (
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
    model: str = "",
) -> Dict[str, str]:
    """构建 TTS 表单数据。

    Args:
        text: 合成文本。
        prompt: 风格提示。
        voice: 声音名称。
        model: 模型名（可选）。

    Returns:
        表单数据字典。
    """
    data: Dict[str, str] = {
        "text": text,
        "voice": voice,
    }
    if prompt:
        data["style"] = prompt
    if model:
        data["model"] = model
    return data
