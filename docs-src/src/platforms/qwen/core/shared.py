from __future__ import annotations

# Qwen core shared constants and utility functions
# This module re-exports everything from the new modular files for backward compatibility.

import json
from typing import Any, Dict, Final, List, Optional, Tuple, Union

from src.logger import get_logger
from src.platforms.qwen.core.constants import (
    BASE_URL,
    CAPS,
    MODELS,
    MODELS_PERSIST_PATH,
    USER_AGENT,
)

logger = get_logger(__name__)

# =============================================================================
# Re-export constants from endpoints (duplicated here for backward compatibility)
# =============================================================================

from src.platforms.qwen.core.endpoints import (
    AUTH_CHECK_PATH,
    BAXIA_SDK_VERSION,
    BXUA_VERSION,
    CHAT_PATH,
    COOKIE_REFRESH_INTERVAL,
    CUSTOM_BASE64_CHARS,
    DELETE_CHAT_PATH,
    FRONTEND_VERSION,
    GENERATED_IMAGE_DIR,
    GENERATED_VIDEO_DIR,
    HASH_FIELDS,
    LOGIN_BATCH,
    LOGIN_BATCH_SIZE,
    LOGIN_CONCURRENCY,
    LOGIN_POLL_INTERVAL,
    LOGIN_POOL_SIZE,
    LOGIN_SELECT_MAX,
    LOGIN_SELECT_MIN,
    MODELS_PATH,
    NEW_CHAT_PATH,
    PERSIST_INTERVAL,
    PERSIST_PATH,
    SEC_CH_UA,
    SIGNIN_PATH,
    SSE_TIMEOUT,
    STOP_CHAT_PATH,
    STS_TOKEN_PATHS,
    SETTINGS_PATH,
    TASK_STATUS_PATH,
    TOKEN_EXPIRY_MARGIN,
    TOKEN_REFRESH_INTERVAL,
    TTS_DIR,
    TTS_PATH,
    TTS_TIMEOUT,
    UPLOAD_TEMP_DIR,
    USE_LOCAL_MODE,
    USER_AGENT_MOBILE,
    VIDEO_CDN_BASE,
    VIDEO_TASK_MAX_POLL_TIME,
    VIDEO_TASK_POLL_INTERVAL,
)

# =============================================================================
# Re-export crypto functions
# =============================================================================
from src.platforms.qwen.core.crypto import (
    custom_encode,
    generate_bxua,
    generate_cookies,
    generate_device_id,
    generate_fingerprint,
    hash_password,
    lzw_compress,
)

# =============================================================================
# Re-export header builders
# =============================================================================
from src.platforms.qwen.core.headers import (
    build_cookie_string,
    build_headers,
    build_login_headers,
    build_stop_headers,
)

# =============================================================================
# Re-export payload builders
# =============================================================================
from src.platforms.qwen.core.payloads import (
    build_i2v_payload,
    build_new_chat_payload,
    build_payload,
    build_replace_content_payload,
    build_stop_payload,
    build_tts_payload,
)

# =============================================================================
# Re-export file object builders
# =============================================================================
from src.platforms.qwen.core.file_objects import (
    build_file_object,
    build_url_file_object,
)

# =============================================================================
# Re-export I/O utilities
# =============================================================================
from src.platforms.qwen.core.io_utils import (
    build_cdn_video_url,
    build_oss_authorization,
    build_wav_from_pcm,
    get_file_category,
    get_mime_type,
    save_image_file,
    save_video_file,
    save_wav_file,
)

# =============================================================================
# Re-export SSE processors
# =============================================================================
from src.platforms.qwen.core.sse import (
    parse_sse_event,
    parse_sse_line,
)

# =============================================================================
# Re-export extract_model_ids (still in shared.py because it's a general utility)
# =============================================================================
def extract_model_ids(raw: Any) -> List[str]:
    """从 API 响应中提取模型 ID 列表。

    支持多种响应格式：
    - OpenAI 兼容: {"data": [{"id": "model-a"}, ...]}
    - 简单列表: {"models": ["model-a", ...]}
    - Qwen 嵌套: {"data": {"models": [{"modelId": "..."}, ...]}}
    - 纯列表: [{"id": "model-a"}, ...]

    Args:
        raw: API 原始 JSON 响应。

    Returns:
        去重的模型 ID 列表。
    """
    models: List[str] = []
    seen: set = set()

    def _add(model_id: str) -> None:
        mid = model_id.strip()
        if mid and mid not in seen:
            models.append(mid)
            seen.add(mid)

    _keys = ("id", "modelId", "model_id", "name")

    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                for key in _keys:
                    if key in item and isinstance(item[key], str):
                        _add(item[key])
                        break
            elif isinstance(item, str):
                _add(item)
        return models

    if not isinstance(raw, dict):
        return models

    data = raw.get("data")

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                for key in _keys:
                    if key in item and isinstance(item[key], str):
                        _add(item[key])
                        break
            elif isinstance(item, str):
                _add(item)
        return models

    if isinstance(data, dict):
        nested = data.get("models", [])
        if isinstance(nested, list):
            for item in nested:
                if isinstance(item, dict):
                    for key in _keys:
                        if key in item and isinstance(item[key], str):
                            _add(item[key])
                            break
                elif isinstance(item, str):
                    _add(item)
        return models

    simple = raw.get("models", [])
    if isinstance(simple, list):
        for item in simple:
            if isinstance(item, str):
                _add(item)
            elif isinstance(item, dict):
                for key in _keys:
                    if key in item and isinstance(item[key], str):
                        _add(item[key])
                        break

    return models


# =============================================================================
# Default settings payload (kept here because it's specific to shared module)
# =============================================================================
DEFAULT_FULL_SETTINGS: Dict[str, Any] = {
    "ui": {
        "notificationEnabled": False,
        "theme": "dark",
        "language": "",
        "chatBubble": True,
        "showUsername": False,
        "widescreenMode": False,
        "title": {"auto": False},
        "autoTags": True,
        "largeTextAsFile": False,
        "splitLargeChunks": False,
        "scrollOnBranchChange": True,
        "responseAutoCopy": False,
        "models": [],
        "richTextInput": False,
    },
    "mcp_remind": False,
    "mcp": {
        "code-interpreter": False,
        "fire-crawl": False,
        "amap": False,
        "image-generation": False,
    },
    "memory": {
        "enable_memory": False,
        "enable_history_memory": False,
        "memory_version_reminder": False,
    },
    "reminder": {"project_version_reminder": False},
    "tts_speaker": {
        "speaker": "Cherry",
        "description": "一位阳光、积极、友好且自然的年轻女士",
        "url": "",
        "gender": "female",
    },
    "tts_speaker_v2": {
        "speaker": "Nini",
        "description": "像糯米糍一样软糯黏腻的嗓音",
        "url": "",
        "gender": "female",
        "is_personal": False,
        "speaker_id": "",
        "spk_name": "邻家妹妹",
    },
    "aipodcast": {"host": "", "guest": ""},
    "code_settings": {
        "custom_prompt": "",
        "diff_display": "split",
        "branch_format": "",
        "last_repo_choice": "",
        "last_branch_choice": "",
    },
    "manage_cookies": None,
    "personalization": {
        "name": "",
        "description": "",
        "style": None,
        "instruction": "",
        "enable_for_new_chat": False,
    },
    "tools_enabled": {
        "web_search": False,
        "web_extractor": False,
        "web_search_image": False,
        "image_gen_tool": True,
        "image_edit_tool": True,
        "code_interpreter": False,
        "bio": False,
        "history_retriever": False,
        "image_zoom_in_tool": False,
    },
}
