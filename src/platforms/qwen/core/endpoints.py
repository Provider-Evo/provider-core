"""Qwen 平台 HTTP 端点常量与基础时间/版本字符串。

仅承担 **常量声明**，不包含任何业务逻辑或 I/O 副作用。
"""

from __future__ import annotations

from typing import Final, List

# ---------------------------------------------------------------------------
# Base URL & API paths
# ---------------------------------------------------------------------------
BASE_URL: Final[str] = "https://chat.qwen.ai"

CHAT_PATH: Final[str] = "/api/v2/chat/completions"
NEW_CHAT_PATH: Final[str] = "/api/v2/chats/new"
STOP_CHAT_PATH: Final[str] = "/api/v2/chat/stop"
DELETE_CHAT_PATH: Final[str] = "/api/v2/chats/{chat_id}"
SIGNIN_PATH: Final[str] = "/api/v1/auths/signin"
AUTH_CHECK_PATH: Final[str] = "/api/v1/auths/"
SETTINGS_PATH: Final[str] = "/api/v2/users/user/settings/update"
MODELS_PATH: Final[str] = "/api/models"
TTS_PATH: Final[str] = "/api/v2/tts/completions"
TASK_STATUS_PATH: Final[str] = "/api/v1/tasks/status/{task_id}"

STS_TOKEN_PATHS: Final[List[str]] = [
    "/api/v2/files/getstsToken",
    "/api/v1/files/getstsToken",
]

# ---------------------------------------------------------------------------
# 客户端版本/特征
# ---------------------------------------------------------------------------
USE_LOCAL_MODE: Final[bool] = True
API_VERSION: Final[str] = "2.1"
FRONTEND_VERSION: Final[str] = "0.2.34"
BAXIA_SDK_VERSION: Final[str] = "2.5.36"
BXUA_VERSION: Final[str] = "231"

USER_AGENT: Final[str] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/148.0.0.0 Safari/537.36"
)
USER_AGENT_MOBILE: Final[str] = (
    "Mozilla/5.0 (Linux; Android 10; BAH3-W09) "
    "AppleWebKit/537.36"
)
SEC_CH_UA: Final[str] = (
    '"Chromium";v="148", "Google Chrome";v="148", '
    '"Not/A)Brand";v="99"'
)

# ---------------------------------------------------------------------------
# 自定义 base64 字符表（用于 LZW 压缩结果编码）
# ---------------------------------------------------------------------------
CUSTOM_BASE64_CHARS: Final[str] = (
    "DGi0YA7BemWnQjCl4_bR3f8SKIF9tUz/xhr2oEOgPpac=61ZqwTudLkM5vHyNXsVJ"
)

# ---------------------------------------------------------------------------
# 周期与超时
# ---------------------------------------------------------------------------
COOKIE_REFRESH_INTERVAL: Final[int] = 15 * 60
PERSIST_INTERVAL: Final[int] = 60
SSE_TIMEOUT: Final[int] = 600
TTS_TIMEOUT: Final[int] = 600
VIDEO_TASK_POLL_INTERVAL: Final[int] = 5
VIDEO_TASK_MAX_POLL_TIME: Final[int] = 600

LOGIN_CONCURRENCY: Final[int] = 5
LOGIN_BATCH: Final[int] = 10

# ---------------------------------------------------------------------------
# 持久化路径
# ---------------------------------------------------------------------------
PERSIST_PATH: Final[str] = "persist/qwen/usage.json"
MODELS_PERSIST_PATH: Final[str] = "persist/qwen/models.json"

# ---------------------------------------------------------------------------
# CDN
# ---------------------------------------------------------------------------
VIDEO_CDN_BASE: Final[str] = "https://cdn.qwenlm.ai/output"

# ---------------------------------------------------------------------------
# 本地输出目录
# ---------------------------------------------------------------------------
TTS_DIR: Final[str] = "data/tts"
GENERATED_IMAGE_DIR: Final[str] = "data/generated_images"
GENERATED_VIDEO_DIR: Final[str] = "data/generated_videos"
UPLOAD_TEMP_DIR: Final[str] = "data/upload_temp"
