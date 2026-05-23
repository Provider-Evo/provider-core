from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Union

BASE_URL: str = "https://translate.google.com"
CHAT_PATH: str = "/_/TranslateWebserverUi/data/batchexecute"
TTS_PATH: str = "/translate_tts"
DEFAULT_MODEL: str = "gtts-default"
GTTS_DEFAULT_LANG: str = "zh-CN"
GTTS_DEFAULT_TLD: str = "com"
GTTS_SLOW: bool = False
GTTS_MAX_CHARS: int = 100


def build_headers(token: str = "") -> Dict[str, str]:
    """构建 gTTS 请求头。

    Args:
        token: 占位 token（gTTS 不需要）。

    Returns:
        请求头字典。
    """
    headers: Dict[str, str] = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://translate.google.com/",
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
    """构建聊天请求体占位。"""
    payload: Dict[str, Any] = {
        "model": model or DEFAULT_MODEL,
        "messages": messages,
        "stream": stream,
    }
    payload.update(kw)
    return payload


def parse_sse_line(data_str: str) -> Optional[Union[str, Dict[str, Any]]]:
    """解析 SSE 行（占位）。"""
    if not data_str or data_str == "[DONE]":
        return None
    try:
        obj = json.loads(data_str)
    except (json.JSONDecodeError, ValueError):
        return None
    choices = obj.get("choices", [])
    if choices:
        delta = choices[0].get("delta", {})
        if delta.get("content"):
            return delta["content"]
    if obj.get("usage"):
        return {"usage": obj["usage"]}
    return None


def build_tts_params(text: str, lang: str, slow: bool) -> Dict[str, str]:
    """构建 gTTS 查询参数。"""
    return {
        "ie": "UTF-8",
        "client": "tw-ob",
        "q": text,
        "tl": lang,
        "ttsspeed": "0.24" if slow else "1",
        "total": "1",
        "idx": "0",
        "textlen": str(len(text)),
    }
