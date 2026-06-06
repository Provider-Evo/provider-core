from __future__ import annotations

"""edgetts 平台常量定义。"""

from typing import Dict, Final, List

MODELS: Final[List[str]] = [
    "zh-CN-XiaoxiaoNeural",
    "zh-CN-YunxiNeural",
    "zh-CN-YunjianNeural",
    "zh-CN-XiaoyiNeural",
    "zh-CN-YunyangNeural",
    "en-US-AriaNeural",
    "en-US-GuyNeural",
    "en-US-JennyNeural",
    "en-US-DavisNeural",
]

CAPS: Final[Dict[str, bool]] = {
    "audio_gen": True,
}

DEFAULT_VOICE: Final[str] = "zh-CN-XiaoxiaoNeural"
DEFAULT_RATE: Final[str] = "+0%"
DEFAULT_VOLUME: Final[str] = "+0%"
DEFAULT_PITCH: Final[str] = "+0Hz"
DEFAULT_FORMAT: Final[str] = "audio-24khz-48kbitrate-mono-mp3"

CHROMIUM_FULL_VERSION: Final[str] = "143.0.3650.75"
CHROMIUM_MAJOR_VERSION: Final[str] = CHROMIUM_FULL_VERSION.split(".", 1)[0]
SEC_MS_GEC_VERSION: Final[str] = "1-{}".format(CHROMIUM_FULL_VERSION)
TRUSTED_CLIENT_TOKEN: Final[str] = "6A5AA1D4EAFF4E9FB37E23D68491D6F4"
WSS_HOST: Final[str] = "speech.platform.bing.com"
WSS_PATH_BASE: Final[str] = (
    "/consumer/speech/synthesize/readaloud/edge/v1"
    "?TrustedClientToken={}".format(TRUSTED_CLIENT_TOKEN)
)

MAX_RETRIES: Final[int] = 3
WIN_EPOCH: Final[int] = 11644473600
S_TO_NS: Final[float] = 1e9

BASE_HEADERS: Final[Dict[str, str]] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/{mv}.0.0.0 Safari/537.36 Edg/{mv}.0.0.0"
    ).format(mv=CHROMIUM_MAJOR_VERSION),
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.9",
}

WSS_HANDSHAKE_HEADERS: Final[Dict[str, str]] = {
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
    "Origin": "chrome-extension://jdiccldimpdaibmpdkjnbmckianbfold",
    **{
        "User-Agent": BASE_HEADERS["User-Agent"],
        "Accept-Encoding": BASE_HEADERS["Accept-Encoding"],
        "Accept-Language": BASE_HEADERS["Accept-Language"],
    },
}
