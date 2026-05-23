from __future__ import annotations

"""gTTS 常量。"""

from typing import Any, Dict, List

MODELS: List[str] = ["gtts-default"]
CAPS: Dict[str, bool] = {
    "audio_gen": True,
}

BASE_URL: str = "https://translate.google.com"
CHAT_PATH: str = "/_/TranslateWebserverUi/data/batchexecute"
TTS_PATH: str = "/translate_tts"

DEFAULT_MODEL: str = "gtts-default"
GTTS_DEFAULT_LANG: str = "zh-CN"
GTTS_DEFAULT_TLD: str = "com"
GTTS_SLOW: bool = False
GTTS_MAX_CHARS: int = 100

MAX_RETRIES: int = 3
