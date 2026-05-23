"""Edge TTS 常量。"""

from __future__ import annotations

from typing import Dict, List

TRUSTED_CLIENT_TOKEN: str = "6A5AA1D4EAFF4E9FB37E23D68491D6F4"
CHROMIUM_FULL_VERSION: str = "143.0.3650.75"
CHROMIUM_MAJOR_VERSION: str = CHROMIUM_FULL_VERSION.split(".", 1)[0]
SEC_MS_GEC_VERSION: str = "1-{}".format(CHROMIUM_FULL_VERSION)

WSS_HOST: str = "speech.platform.bing.com"
WSS_PATH_BASE: str = (
    "/consumer/speech/synthesize/readaloud/edge/v1"
    "?TrustedClientToken={}".format(TRUSTED_CLIENT_TOKEN)
)

DEFAULT_VOICE: str = "zh-CN-XiaoxiaoNeural"
WIN_EPOCH: int = 11644473600
S_TO_NS: float = 1e9
MAX_RETRIES: int = 3

MODELS: List[str] = ["en-US-EmmaMultilingualNeural"]
CAPS: Dict[str, bool] = {
    "audio_gen": True,
}
