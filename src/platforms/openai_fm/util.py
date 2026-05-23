from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Union

BASE_URL: str = "https://www.openai.fm"
CHAT_PATH: str = "/api/generate"
API_ENDPOINT: str = "https://www.openai.fm/api/generate"
VOICES: List[str] = [
    "alloy",
    "ash",
    "ballad",
    "coral",
    "echo",
    "fable",
    "onyx",
    "nova",
    "sage",
    "shimmer",
    "verse",
]
STYLES: List[str] = [
    "friendly",
    "patient_teacher",
    "noir_detective",
    "cowboy",
    "calm",
    "scientific_style",
]
DEFAULT_VOICE: str = "coral"
DEFAULT_STYLE: str = "calm"
DEFAULT_MODEL: str = "tts-1"

STYLE_PROMPTS: Dict[str, str] = {
    "friendly": (
        "Affect/personality: A cheerful guide\n\n"
        "Tone: Friendly, clear, and reassuring, creating a calm atmosphere and making "
        "the listener feel confident and comfortable.\n\n"
        "Pronunciation: Clear, articulate, and steady, ensuring each instruction is easily "
        "understood while maintaining a natural, conversational flow.\n\n"
        "Pause: Brief, purposeful pauses after key instructions to allow time for the "
        "listener to process the information and follow along.\n\n"
        "Emotion: Warm and supportive, conveying empathy and care, ensuring the listener "
        "feels guided and safe throughout the journey."
    ),
    "patient_teacher": (
        "Accent/Affect: Warm, refined, and gently instructive, reminiscent of a friendly art instructor.\n\n"
        "Tone: Calm, encouraging, and articulate, clearly describing each step with patience.\n\n"
        "Pacing: Slow and deliberate, pausing often to allow the listener to follow instructions comfortably.\n\n"
        "Emotion: Cheerful, supportive, and pleasantly enthusiastic; convey genuine enjoyment and appreciation.\n\n"
        "Pronunciation: Clearly articulate terminology with gentle emphasis.\n\n"
        "Personality Affect: Friendly and approachable with a hint of sophistication."
    ),
    "noir_detective": (
        "Affect: a mysterious noir detective\n\n"
        "Tone: Cool, detached, but subtly reassuring.\n\n"
        "Delivery: Slow and deliberate, with dramatic pauses to build suspense.\n\n"
        "Emotion: A mix of world-weariness and quiet determination, with just a hint of dry humor.\n\n"
        "Punctuation: Short, punchy sentences with ellipses and dashes to create rhythm and tension."
    ),
    "cowboy": (
        "Voice: Warm, relaxed, and friendly, with a steady cowboy drawl that feels approachable.\n\n"
        "Punctuation: Light and natural, with gentle pauses that create a conversational rhythm.\n\n"
        "Delivery: Smooth and easygoing, with a laid-back pace that reassures the listener.\n\n"
        "Phrasing: Simple, direct, and folksy, using casual, familiar language.\n\n"
        "Tone: Lighthearted and welcoming, with a calm confidence that puts the caller at ease."
    ),
    "calm": (
        "Voice Affect: Calm, composed, and reassuring; project quiet authority and confidence.\n\n"
        "Tone: Sincere, empathetic, and gently authoritative.\n\n"
        "Pacing: Steady and moderate; unhurried enough to communicate care.\n\n"
        "Emotion: Genuine empathy and understanding; speak with warmth.\n\n"
        "Pronunciation: Clear and precise, emphasizing key reassurances.\n\n"
        "Pauses: Brief pauses after offering assistance or requesting details."
    ),
    "scientific_style": (
        "Voice: Authoritative and precise, with a measured, academic tone.\n\n"
        "Tone: Formal and analytical, maintaining objectivity while conveying complex information.\n\n"
        "Pacing: Moderate and deliberate, allowing time for complex concepts to be processed.\n\n"
        "Pronunciation: Precise articulation of technical terms and scientific vocabulary.\n\n"
        "Pauses: Strategic pauses after introducing new concepts to allow for comprehension.\n\n"
        "Emotion: Restrained enthusiasm for discoveries and findings."
    ),
}


def build_headers(token: str = "") -> Dict[str, str]:
    """构建 openai.fm 请求头。

    Args:
        token: Cookie 或鉴权字符串。

    Returns:
        请求头字典。
    """
    headers: Dict[str, str] = {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "origin": "https://www.openai.fm",
        "referer": "https://www.openai.fm/worker-20260303-rate-limit.js",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
        ),
    }
    if token:
        headers["Cookie"] = token
    return headers


def build_payload(
    messages: List[Dict[str, Any]],
    model: str = "",
    stream: bool = True,
    tools: Optional[List[Dict[str, Any]]] = None,
    **kw: Any,
) -> Dict[str, Any]:
    """构建聊天请求体（占位，openai.fm 主要用于 TTS）。"""
    payload: Dict[str, Any] = {
        "model": model or DEFAULT_MODEL,
        "messages": messages,
        "stream": stream,
    }
    if tools:
        payload["tools"] = tools
    payload.update(kw)
    return payload


def parse_sse_line(data_str: str) -> Optional[Union[str, Dict[str, Any]]]:
    """解析 SSE data 行。"""
    if not data_str or data_str == "[DONE]":
        return None
    try:
        obj = json.loads(data_str)
    except (json.JSONDecodeError, ValueError):
        return None
    if "error" in obj:
        raise ValueError("SSE error: {}".format(obj["error"]))
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


def build_tts_form_data(
    input_text: str,
    prompt: str,
    voice: str,
    vibe: str = "",
) -> Dict[str, str]:
    """构建 TTS multipart/form-data 字段。"""
    return {
        "input": input_text,
        "prompt": prompt,
        "voice": voice,
        "vibe": vibe,
    }
