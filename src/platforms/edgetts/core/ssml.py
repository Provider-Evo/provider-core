"""Edge TTS SSML 构造。"""

from __future__ import annotations


def build_ssml(text: str, voice: str) -> str:
    """构建 Edge TTS SSML 字符串。

    Args:
        text: 待合成文本。
        voice: 声音名称。

    Returns:
        SSML 字符串。
    """
    locale = "en-US"
    parts = voice.split("-", 2)
    if len(parts) >= 2:
        locale = "{}-{}".format(parts[0], parts[1])
    ssml = (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        'xmlns:mstts="http://www.w3.org/2001/mstts" xml:lang="{locale}">'
        '<voice name="{voice}" xml:lang="{locale}" xml:gender="Female">'
        '<mstts:express-as style="general">{text}</mstts:express-as>'
        "</voice></speak>"
    ).format(locale=locale, voice=voice, text=text)
    return ssml


def _remove_incompatible_characters(string: str) -> str:
    """移除不兼容的控制字符。

    Args:
        string: 原始字符串。

    Returns:
        清理后的字符串。
    """
    chars = list(string)
    for idx, ch in enumerate(chars):
        code = ord(ch)
        if (0 <= code <= 8) or (11 <= code <= 12) or (14 <= code <= 31):
            chars[idx] = " "
    return "".join(chars)


def mkssml(voice: str, rate: str, volume: str, pitch: str, text: str) -> str:
    """构建带音调控制的 SSML。

    Args:
        voice: 声音名称。
        rate: 语速。
        volume: 音量。
        pitch: 音调。
        text: 待合成文本。

    Returns:
        SSML 字符串。
    """
    cleaned = _remove_incompatible_characters(text)
    return (
        "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'>"
        "<voice name='{voice}'><prosody pitch='{pitch}' rate='{rate}' volume='{volume}'>"
        "{text}</prosody></voice></speak>"
    ).format(voice=voice, pitch=pitch, rate=rate, volume=volume, text=cleaned)
