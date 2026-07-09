"""openaifm 平台常量定义。"""

from __future__ import annotations

from typing import Dict, Final, List

BASE_URL: Final[str] = "https://www.openai.fm"
GENERATE_PATH: Final[str] = "/api/generate"

USER_AGENT: Final[str] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/149.0.0.0 Safari/537.36"
)

# 声音列表（openai.fm 实际可用的 voice 名称）
VOICES: Final[List[str]] = [
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

# 模型列表（对 TTS 平台来说，voice 即模型）
MODELS: Final[List[str]] = list(VOICES)

CAPS: Final[Dict[str, bool]] = {
    "audio_gen": True,
}

DEFAULT_VOICE: Final[str] = "alloy"
DEFAULT_STYLE: Final[str] = "calm"

STYLES: Final[List[str]] = [
    "friendly",
    "patient_teacher",
    "noir_detective",
    "cowboy",
    "calm",
    "scientific_style",
]

STYLE_PROMPTS: Final[Dict[str, str]] = {
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
