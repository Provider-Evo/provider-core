from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Union
import secrets

BASE_URL: str = "https://speech.platform.bing.com/consumer/speech/synthesize/readaloud"
CHAT_PATH: str = "/edge/v1"
TRUSTED_CLIENT_TOKEN: str = "6A5AA1D4EAFF4E9FB37E23D68491D6F4"
CHROMIUM_FULL_VERSION: str = "143.0.3650.75"
CHROMIUM_MAJOR_VERSION: str = CHROMIUM_FULL_VERSION.split(".", 1)[0]
SEC_MS_GEC_VERSION: str = "1-{}".format(CHROMIUM_FULL_VERSION)


def build_headers(token: str = "") -> Dict[str, str]:
    """构建 WebSocket/HTTP 请求头。

    Args:
        token: 预留的鉴权令牌（edge tts 当前无需）。

    Returns:
        请求头字典。
    """
    headers: Dict[str, str] = {
        "Origin": "chrome-extension://jdiccldimpdaibmpdkjnbmckianbfold",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/{}.0.0.0 Safari/537.36 Edg/{}.0.0.0".format(
                CHROMIUM_MAJOR_VERSION, CHROMIUM_MAJOR_VERSION
            )
        ),
        "Accept": "*/*",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Host": "speech.platform.bing.com",
        "Cookie": "muid={};".format(secrets.token_hex(16).upper()),
    }
    if token:
        headers["Authorization"] = token
    return headers


def build_payload(
    messages: List[Dict[str, Any]],
    model: str = "",
    stream: bool = True,
    **kw: Any,
) -> Dict[str, Any]:
    """构建聊天请求体占位（Edge TTS 主要用于语音合成）。

    Args:
        messages: 消息列表。
        model: 模型名。
        stream: 是否流式。
        **kw: 其他字段。

    Returns:
        请求体字典。
    """
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": stream,
    }
    payload.update(kw)
    return payload


def parse_sse_line(data_str: str) -> Optional[Union[str, Dict[str, Any]]]:
    """解析 SSE 行（占位，方便与模板保持一致）。

    Args:
        data_str: data 段字符串。

    Returns:
        文本片段、字典或 None。
    """
    if not data_str or data_str == "[DONE]":
        return None
    try:
        obj = json.loads(data_str)
    except (json.JSONDecodeError, ValueError):
        return None
    choices = obj.get("choices", [])
    if not choices:
        if obj.get("usage"):
            return {"usage": obj["usage"]}
        return None
    delta = choices[0].get("delta", {})
    content = delta.get("content")
    if content:
        return content
    reasoning = delta.get("reasoning_content") or delta.get("thinking")
    if reasoning:
        return {"thinking": reasoning}
    if obj.get("usage"):
        return {"usage": obj["usage"]}
    return None


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
        "<speak version=\"1.0\" xmlns=\"http://www.w3.org/2001/10/synthesis\" "
        "xmlns:mstts=\"http://www.w3.org/2001/mstts\" xml:lang=\"{locale}\">"
        "<voice name=\"{voice}\" xml:lang=\"{locale}\" xml:gender=\"Female\">"
        "<mstts:express-as style=\"general\">{text}</mstts:express-as>"
        "</voice></speak>"
    ).format(locale=locale, voice=voice, text=text)
    return ssml
