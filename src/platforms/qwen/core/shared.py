from __future__ import annotations

# Qwen core 共享常量与工具函数
import base64
import hashlib
import hmac as _hmac
import json
import os
import secrets
import struct
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Final, List, Optional, Tuple, Union

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

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
# 常量
# =============================================================================
CHAT_PATH: Final[str] = "/api/v2/chat/completions"
NEW_CHAT_PATH: Final[str] = "/api/v2/chats/new"
STOP_CHAT_PATH: Final[str] = "/api/v2/chat/stop"
DELETE_CHAT_PATH: Final[str] = "/api/v2/chats/{chat_id}"
SIGNIN_PATH: Final[str] = "/api/v1/auths/signin"
AUTH_CHECK_PATH: Final[str] = "/api/v1/auths/"
SETTINGS_PATH: Final[str] = "/api/v2/users/user/settings/update"
MODELS_PATH: Final[str] = "/api/models"
STS_TOKEN_PATHS: Final[List[str]] = [
    "/api/v2/files/getstsToken",
    "/api/v1/files/getstsToken",
]
TTS_PATH: Final[str] = "/api/v2/tts/completions"
TASK_STATUS_PATH: Final[str] = "/api/v1/tasks/status/{task_id}"

USE_LOCAL_MODE: Final[bool] = True
API_VERSION: Final[str] = "2.1"
FRONTEND_VERSION: Final[str] = "0.2.34"
BAXIA_SDK_VERSION: Final[str] = "2.5.36"
BXUA_VERSION: Final[str] = "231"

USER_AGENT_MOBILE: Final[str] = (
    "Mozilla/5.0 (Linux; Android 10; BAH3-W09) "
    "AppleWebKit/537.36"
)
SEC_CH_UA: Final[str] = (
    '"Chromium";v="148", "Google Chrome";v="148", '
    '"Not/A)Brand";v="99"'
)
CUSTOM_BASE64_CHARS: Final[str] = (
    "DGi0YA7BemWnQjCl4_bR3f8SKIF9tUz/xhr2oEOgPpac=61ZqwTudLkM5vHyNXsVJ"
)
COOKIE_REFRESH_INTERVAL: Final[int] = 15 * 60
TOKEN_REFRESH_INTERVAL: Final[int] = 30 * 60  # 每 30 分钟检查一次 Token 过期
TOKEN_EXPIRY_MARGIN: Final[int] = 3600  # Token 在过期前 1 小时内视为即将过期
HASH_FIELDS: Final[Dict[int, str]] = {
    16: "split",
    17: "full",
    18: "full",
    31: "full",
    34: "full",
    36: "full",
}

# 持久化与任务配置
PERSIST_PATH: Final[str] = "persist/qwen/usage.json"
TASK_TIMERS_PATH: Final[str] = "persist/qwen/task_timers.json"
LOGIN_CONCURRENCY: Final[int] = 5
LOGIN_BATCH: Final[int] = 10
PERSIST_INTERVAL: Final[int] = 60
LOGIN_POLL_INTERVAL: Final[int] = 1800      # 30 min between poll cycles
LOGIN_BATCH_SIZE: Final[int] = 10           # accounts to login per cycle
LOGIN_POOL_SIZE: Final[int] = 100           # max candidates in selection pool
LOGIN_SELECT_MIN: Final[int] = 15           # min random selection from pool
LOGIN_SELECT_MAX: Final[int] = 30           # max random selection from pool
INITIAL_LOGIN_MAX: Final[int] = 50          # max accounts in initial startup pass
SSE_TIMEOUT: Final[int] = 600
TTS_TIMEOUT: Final[int] = 600
VIDEO_TASK_POLL_INTERVAL: Final[int] = 5
VIDEO_TASK_MAX_POLL_TIME: Final[int] = 600
VIDEO_CDN_BASE: Final[str] = "https://cdn.qwenlm.ai/output"

# 本地输出目录
TTS_DIR: Final[str] = "data/tts"
GENERATED_IMAGE_DIR: Final[str] = "data/generated_images"
GENERATED_VIDEO_DIR: Final[str] = "data/generated_videos"
UPLOAD_TEMP_DIR: Final[str] = "data/upload_temp"

# 文件类型映射
FILE_TYPE_MAPPING: Final[Dict[str, str]] = {
    "image/jpeg": "image", "image/jpg": "image",
    "image/png": "image", "image/gif": "image",
    "image/webp": "image", "image/bmp": "image",
    "video/mp4": "video", "video/avi": "video",
    "video/mov": "video", "video/quicktime": "video",
    "audio/mpeg": "audio", "audio/mp3": "audio",
    "audio/wav": "audio", "audio/x-wav": "audio",
    "audio/aac": "audio", "audio/ogg": "audio",
    "audio/m4a": "audio", "audio/opus": "audio",
    "application/pdf": "file",
    "text/plain": "file", "text/csv": "file",
    "application/json": "file",
}
EXTENSION_TO_MIME: Final[Dict[str, str]] = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png", ".gif": "image/gif",
    ".webp": "image/webp", ".bmp": "image/bmp",
    ".mp4": "video/mp4", ".avi": "video/avi",
    ".mov": "video/quicktime",
    ".mp3": "audio/mpeg", ".wav": "audio/wav",
    ".aac": "audio/aac", ".ogg": "audio/ogg",
    ".m4a": "audio/m4a", ".opus": "audio/opus",
    ".pdf": "application/pdf",
    ".txt": "text/plain", ".csv": "text/csv",
    ".json": "application/json",
    ".md": "text/markdown", ".yaml": "text/yaml",
    ".py": "text/x-python",
}

# 默认完整设置载荷（关闭记忆等功能）
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


# =============================================================================
# LZW 压缩 + 自定义编码
# =============================================================================
def lzw_compress(
    data: str,
    bits: int,
    char_func: Callable[[int], str],
) -> str:
    """执行 LZW 压缩。

    Args:
        data: 待压缩字符串。
        bits: 每个字符的位数。
        char_func: 索引到字符的映射函数。

    Returns:
        压缩后的字符串。
    """
    if not data:
        return ""

    dictionary: Dict[str, int] = {}
    dict_to_create: Dict[str, bool] = {}
    w: str = ""
    enlarge_in: int = 2
    dict_size: int = 3
    num_bits: int = 2
    result: List[str] = []
    val: int = 0
    pos: int = 0

    def _write(v: int, p: int, code: int, bc: int) -> Tuple[int, int]:
        for _ in range(bc):
            v = (v << 1) | (code & 1)
            if p == bits - 1:
                p = 0
                result.append(char_func(v))
                v = 0
            else:
                p += 1
            code >>= 1
        return v, p

    def _zeros(v: int, p: int, count: int) -> Tuple[int, int]:
        for _ in range(count):
            v <<= 1
            if p == bits - 1:
                p = 0
                result.append(char_func(v))
                v = 0
            else:
                p += 1
        return v, p

    def _new_char(v: int, p: int, ch: str, nb: int) -> Tuple[int, int]:
        cp = ord(ch)
        if cp < 256:
            v, p = _zeros(v, p, nb)
            v, p = _write(v, p, cp, 8)
        else:
            marker = 1
            for _ in range(nb):
                v = (v << 1) | marker
                if p == bits - 1:
                    p = 0
                    result.append(char_func(v))
                    v = 0
                else:
                    p += 1
                marker = 0
            v, p = _write(v, p, cp, 16)
        return v, p

    for c in data:
        if c not in dictionary:
            dictionary[c] = dict_size
            dict_size += 1
            dict_to_create[c] = True
        wc = w + c
        if wc in dictionary:
            w = wc
        else:
            if w in dict_to_create:
                val, pos = _new_char(val, pos, w[0], num_bits)
                enlarge_in -= 1
                if enlarge_in == 0:
                    enlarge_in = 2 ** num_bits
                    num_bits += 1
                del dict_to_create[w]
            else:
                val, pos = _write(val, pos, dictionary[w], num_bits)
                enlarge_in -= 1
                if enlarge_in == 0:
                    enlarge_in = 2 ** num_bits
                    num_bits += 1
            dictionary[wc] = dict_size
            dict_size += 1
            w = c

    if w:
        if w in dict_to_create:
            val, pos = _new_char(val, pos, w[0], num_bits)
            enlarge_in -= 1
            if enlarge_in == 0:
                enlarge_in = 2 ** num_bits
                num_bits += 1
            del dict_to_create[w]
        else:
            val, pos = _write(val, pos, dictionary[w], num_bits)
            enlarge_in -= 1
            if enlarge_in == 0:
                enlarge_in = 2 ** num_bits
                num_bits += 1

    val, pos = _write(val, pos, 2, num_bits)
    while True:
        val <<= 1
        if pos == bits - 1:
            result.append(char_func(val))
            break
        pos += 1

    return "".join(result)


def custom_encode(data: str, url_safe: bool = True) -> str:
    """使用自定义字符集编码数据。

    Args:
        data: 待编码字符串。
        url_safe: 是否 URL 安全模式。

    Returns:
        编码后的字符串。
    """
    if not data:
        return ""
    cs = CUSTOM_BASE64_CHARS
    compressed = lzw_compress(data, 6, lambda idx: cs[idx])
    if not url_safe:
        rem = len(compressed) % 4
        padding_map = {1: "===", 2: "==", 3: "="}
        compressed += padding_map.get(rem, "")
    return compressed


# =============================================================================
# 指纹生成
# =============================================================================
def generate_device_id() -> str:
    """生成 20 字符十六进制设备 ID。

    Returns:
        设备 ID 字符串。
    """
    return "".join(
        secrets.choice("0123456789abcdef") for _ in range(20)
    )


def _generate_hash() -> int:
    """生成随机 32 位哈希值。

    Returns:
        随机无符号 32 位整数。
    """
    return secrets.randbelow(0x100000000)


def generate_fingerprint(device_id: Optional[str] = None) -> str:
    """生成浏览器指纹字符串（随机数+时间戳副作用）。n
    注意：此函数涉及随机数生成(_generate_hash())和time.time()时间戳。
    在client.py的init()中调用并存储（_fp），用于后续请求头生成。

    Args:
        device_id: 设备 ID，为 None 则自动生成。

    Returns:
        以 ^ 分隔的 37 字段指纹字符串。
    """
    did = device_id or generate_device_id()
    current_timestamp = int(time.time() * 1000)
    fields: List[str] = [
        did,
        "websdk-2.3.15d",
        "1765348410850",
        "91",
        "1|15",
        "zh-CN",
        "-480",
        "16705151|12791",
        "1470|956|283|797|158|0|1470|956|1470|798|0|0",
        "5",
        "MacIntel",
        "10",
        (
            "ANGLE (Apple, ANGLE Metal Renderer: Apple M4, "
            "Unspecified Version)|Google Inc. (Apple)"
        ),
        "30|30",
        "0",
        "28",
        "5|{}".format(_generate_hash()),
        str(_generate_hash()),
        str(_generate_hash()),
        "1",
        "0",
        "1",
        "0",
        "P",
        "0",
        "0",
        "0",
        "416",
        "Google Inc.",
        "8",
        "-1|0|0|0|0",
        str(_generate_hash()),
        "11",
        str(current_timestamp),
        str(_generate_hash()),
        "0",
        str(secrets.randbelow(91) + 10),
    ]
    return "^".join(fields)


# =============================================================================
# Cookie 生成
# =============================================================================
def _process_fingerprint_fields(fields: List[str]) -> List[str]:
    """处理指纹字段用于 Cookie 生成。

    Args:
        fields: 指纹字段列表。

    Returns:
        处理后的字段列表。
    """
    processed = list(fields)
    ts_now = int(time.time() * 1000)
    for idx, ft in HASH_FIELDS.items():
        if idx >= len(processed):
            continue
        if ft == "split":
            parts = processed[idx].split("|")
            if len(parts) == 2:
                processed[idx] = "{}|{}".format(parts[0], _generate_hash())
        elif ft == "full":
            if idx == 36:
                processed[idx] = str(secrets.randbelow(91) + 10)
            else:
                processed[idx] = str(_generate_hash())
    if 33 < len(processed):
        processed[33] = str(ts_now)
    return processed


def generate_cookies(
    fingerprint: Optional[str] = None,
) -> Dict[str, Any]:
    """生成 SSXMOD Cookie 字典（随机数+时间戳副作用）。

    注意：此函数涉及随机数生成(_generate_hash())和time.time()时间戳。
    在client.py的init()中调用并存储(_cookies)，用于后续请求。

    Args:
        fingerprint: 指纹字符串，为 None 则自动生成。

    Returns:
        包含 ssxmod_itna、ssxmod_itna2、timestamp 的字典。
    """
    fp_data = fingerprint or generate_fingerprint()
    fields = fp_data.split("^")
    processed = _process_fingerprint_fields(fields)

    itna_data = "^".join(processed)
    ssxmod_itna = "1-" + custom_encode(itna_data, url_safe=True)

    itna2_fields = [
        processed[0], processed[1], processed[23], "0",
        "", "0", "", "", "0", "0", "0",
        processed[32], processed[33], "0", "0", "0", "0", "0",
    ]
    itna2_data = "^".join(itna2_fields)
    ssxmod_itna2 = "1-" + custom_encode(itna2_data, url_safe=True)

    timestamp = int(processed[33])
    return {
        "ssxmod_itna": ssxmod_itna,
        "ssxmod_itna2": ssxmod_itna2,
        "timestamp": timestamp,
    }


# =============================================================================
# BX-UA 生成
# =============================================================================
def _derive_key_iv(seed: str) -> Tuple[bytes, bytes]:
    """从种子派生 AES-CBC 密钥和 IV。

    Args:
        seed: 种子字符串。

    Returns:
        (key, iv) 各 16 字节。
    """
    digest = hashlib.sha256(seed.encode()).digest()
    return digest[:16], digest[16:32]


def _encrypt_aes_cbc(data: bytes, key: bytes, iv: bytes) -> bytes:
    """AES-CBC 加密并填充。

    Args:
        data: 待加密数据。
        key: 16 字节密钥。
        iv: 16 字节初始化向量。

    Returns:
        加密后的字节数据。
    """
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return cipher.encrypt(pad(data, AES.block_size))


def generate_bxua(
    fingerprint: str,
    version: str = BXUA_VERSION,
    timestamp: Optional[int] = None,
    seed: Optional[str] = None,
) -> str:
    """生成 bx-ua 请求头值。

    Args:
        fingerprint: 指纹字符串。
        version: BX-UA 版本号。
        timestamp: 毫秒时间戳，为 None 则用当前时间。
        seed: 加密种子，为 None 则用指纹本身。

    Returns:
        格式为 "version!base64_encrypted" 的字符串。
    """
    ts = timestamp or int(time.time() * 1000)
    fields = fingerprint.split("^")
    rnd = secrets.randbelow(9000) + 1000
    cs_input = "{}{}{}".format(fingerprint, ts, rnd)
    cs = hashlib.md5(cs_input.encode()).hexdigest()[:8]

    payload_dict: Dict[str, Any] = {
        "v": version,
        "ts": ts,
        "fp": fingerprint,
        "d": {
            "deviceId": fields[0] if len(fields) > 0 else "",
            "sdkVer": fields[1] if len(fields) > 1 else "",
            "lang": fields[5] if len(fields) > 5 else "",
            "tz": fields[6] if len(fields) > 6 else "",
            "platform": fields[10] if len(fields) > 10 else "",
            "renderer": fields[12] if len(fields) > 12 else "",
            "mode": fields[23] if len(fields) > 23 else "",
            "vendor": fields[28] if len(fields) > 28 else "",
        },
        "rnd": rnd,
        "seq": 1,
        "cs": cs,
    }
    payload_bytes = json.dumps(
        payload_dict, separators=(",", ":")
    ).encode()
    key, iv = _derive_key_iv(seed or fingerprint)
    encrypted = _encrypt_aes_cbc(payload_bytes, key, iv)
    encoded = base64.b64encode(encrypted).decode("ascii")
    return "{}!{}".format(version, encoded)


# =============================================================================
# 请求头构建
# =============================================================================
def build_headers(
    token: str,
    *,
    chat_id: Optional[str] = None,
    include_sse: bool = False,
    fingerprint: Optional[str] = None,
    cookies: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """构建通用请求头。

    Args:
        token: Bearer 令牌。
        chat_id: 对话 ID，用于 Referer。
        include_sse: 是否包含 SSE 相关头。
        fingerprint: 指纹字符串，为 None 则自动生成。
        cookies: Cookie 字典，为 None 则自动生成。

    Returns:
        请求头字典。
    """
    if USE_LOCAL_MODE or chat_id is None:
        referer = "{}/c/local".format(BASE_URL)
    else:
        referer = "{}/c/{}".format(BASE_URL, chat_id)

    fp = fingerprint or generate_fingerprint()
    if cookies is None:
        cookies = generate_cookies(fp)

    h: Dict[str, str] = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "Cookie": build_cookie_string(token, cookies),
        "Host": "chat.qwen.ai",
        "Origin": BASE_URL,
        "Referer": referer,
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Timezone": time.strftime("%a %b %d %Y %H:%M:%S GMT%z"),
        "User-Agent": USER_AGENT,
        "Version": FRONTEND_VERSION,
        "X-Request-Id": str(uuid.uuid4()),
        "authorization": "Bearer {}".format(token),
        "bx-ua": generate_bxua(fp),
        "bx-v": BAXIA_SDK_VERSION,
        "sec-ch-ua": SEC_CH_UA,
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "source": "web",
    }
    if include_sse:
        h["X-Accel-Buffering"] = "no"
    return h


def build_login_headers() -> Dict[str, str]:
    """构建登录请求头。

    Returns:
        登录专用请求头字典。
    """
    return {
        "Host": "chat.qwen.ai",
        "Content-Type": "application/json;charset=UTF-8",
        "User-Agent": USER_AGENT_MOBILE,
        "Accept": "*/*",
        "Origin": BASE_URL,
        "Referer": "{}/auth?action=signin".format(BASE_URL),
    }


def build_stop_headers(token: str) -> Dict[str, str]:
    """构建停止生成请求头。

    Args:
        token: Bearer 令牌。

    Returns:
        停止生成专用请求头字典。
    """
    return {
        "Accept": "application/json",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "Host": "chat.qwen.ai",
        "Origin": BASE_URL,
        "Referer": "{}/c/local".format(BASE_URL),
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": USER_AGENT,
        "X-Request-Id": str(uuid.uuid4()),
        "authorization": "Bearer {}".format(token),
        "source": "web",
    }


def build_cookie_string(
    token: str,
    cookies: Optional[Dict[str, Any]] = None,
) -> str:
    """构建 Cookie 请求头字符串。

    Args:
        token: Bearer 令牌。
        cookies: Cookie 字典，为 None 则自动生成。

    Returns:
        分号分隔的 Cookie 字符串。
    """
    if cookies is None:
        cookies = generate_cookies()
    return "; ".join([
        "token={}".format(token),
        "ssxmod_itna={}".format(cookies.get("ssxmod_itna", "")),
        "ssxmod_itna2={}".format(cookies.get("ssxmod_itna2", "")),
    ])


# =============================================================================
# 请求体构建
# =============================================================================
def build_payload(
    messages: List[Dict[str, Any]],
    model: str,
    chat_id: str,
    *,
    files: Optional[List[Dict[str, Any]]] = None,
    chat_type: str = "t2t",
    sub_chat_type: Optional[str] = None,
    parent_id: Optional[str] = None,
    thinking_enabled: bool = True,
    auto_thinking: bool = True,
    thinking_mode: str = "Auto",
    thinking_format: str = "summary",
    auto_search: bool = False,
    stream: bool = True,
) -> Dict[str, Any]:
    """构建聊天补全请求载荷。

    将 OpenAI 格式 messages 转换为 Qwen 内部消息格式，
    支持多模态内容（文本、图片 URL、base64 图片）。

    Args:
        messages: OpenAI 格式消息列表。
        model: 模型名称。
        chat_id: 对话 ID。
        files: 文件对象列表（已上传到 OSS 的文件信息）。
        chat_type: 聊天类型（t2t/t2i/i2v）。
        sub_chat_type: 子聊天类型。
        parent_id: 父消息 ID。
        thinking_enabled: 是否启用思考。
        auto_thinking: 是否自动思考。
        thinking_mode: 思考模式名称。
        thinking_format: 思考格式。
        auto_search: 是否自动搜索。
        stream: 是否流式。

    Returns:
        完整请求载荷字典。
    """
    if files is None:
        files = []
    if sub_chat_type is None:
        sub_chat_type = chat_type

    # 提取所有用户消息内容，支持多模态（处理所有历史消息中的文件）
    all_text_parts: List[str] = []
    extra_files: List[Dict[str, Any]] = []

    for msg in messages:
        if msg.get("role") != "user":
            continue
        msg_content = msg.get("content", "")
        if isinstance(msg_content, str):
            all_text_parts.append(msg_content)
        elif isinstance(msg_content, list):
            for part in msg_content:
                if not isinstance(part, dict):
                    continue
                part_type = part.get("type", "")
                if part_type == "text":
                    all_text_parts.append(part.get("text", ""))
                elif part_type == "image_url":
                    img_url_obj = part.get("image_url", {})
                    img_url = (
                        img_url_obj.get("url", "")
                        if isinstance(img_url_obj, dict)
                        else str(img_url_obj)
                    )
                    # 跳过 base64 data URI（已通过 OSS 上传处理）
                    if img_url and not img_url.startswith("data:"):
                        extra_files.append(
                            _build_url_file_object(img_url, "image")
                        )
                elif part_type == "video_url":
                    video_url_obj = part.get("video_url", {})
                    video_url = (
                        video_url_obj.get("url", "")
                        if isinstance(video_url_obj, dict)
                        else str(video_url_obj)
                    )
                    if video_url and not video_url.startswith("data:"):
                        extra_files.append(
                            _build_url_file_object(video_url, "video")
                        )
                elif part_type == "input_audio":
                    audio_obj = part.get("input_audio", {})
                    audio_url = audio_obj.get("url", "")
                    if audio_url and not audio_url.startswith("data:"):
                        extra_files.append(
                            _build_url_file_object(audio_url, "audio")
                        )
                    # data URI 类型由 upload_files 路径处理

    content = "\n".join(filter(None, all_text_parts))

    # 合并文件列表
    all_files = list(files) + extra_files

    feature_config: Dict[str, Any] = {
        "thinking_enabled": thinking_enabled,
        "output_schema": "phase",
        "research_mode": "normal",
        "auto_thinking": auto_thinking,
        "thinking_mode": thinking_mode,
        "auto_search": auto_search,
    }
    if thinking_enabled:
        feature_config["thinking_format"] = thinking_format

    fid = str(uuid.uuid4())
    child_id = str(uuid.uuid4())
    msg_timestamp = int(time.time())

    message_obj: Dict[str, Any] = {
        "fid": fid,
        "parentId": parent_id,
        "childrenIds": [child_id],
        "role": "user",
        "content": content,
        "user_action": "chat",
        "files": all_files,
        "timestamp": msg_timestamp,
        "models": [model],
        "chat_type": chat_type,
        "feature_config": feature_config,
        "extra": {"meta": {"subChatType": sub_chat_type}},
        "sub_chat_type": sub_chat_type,
        "parent_id": parent_id,
    }

    return {
        "stream": stream,
        "version": API_VERSION,
        "incremental_output": True,
        "chat_id": chat_id,
        "chat_mode": "local" if USE_LOCAL_MODE else "normal",
        "model": model,
        "parent_id": parent_id,
        "messages": [message_obj],
        "timestamp": msg_timestamp + 1,
    }


def build_i2v_payload(
    prompt: str,
    chat_id: str,
    model: str,
    image_url: str,
    image_name: str,
    size: str,
    parent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """构建图片到视频（i2v）专用请求载荷。

    Args:
        prompt: 视频生成描述。
        chat_id: 对话 ID。
        model: 模型名称。
        image_url: 参考图片 URL（已上传到 OSS）。
        image_name: 图片文件名。
        size: 视频尺寸（16:9/9:16/1:1）。
        parent_id: 父消息 ID。

    Returns:
        i2v 请求载荷字典。
    """
    fid = str(uuid.uuid4())
    child_id = str(uuid.uuid4())
    msg_ts = int(time.time())

    file_obj: Dict[str, Any] = {
        "type": "image",
        "name": image_name,
        "file_type": "image/png",
        "showType": "image",
        "file_class": "vision",
        "url": image_url,
        "isQuote": True,
    }

    feature_config: Dict[str, Any] = {
        "thinking_enabled": True,
        "output_schema": "phase",
        "research_mode": "normal",
        "auto_thinking": False,
        "thinking_mode": "Thinking",
    }

    message_obj: Dict[str, Any] = {
        "fid": fid,
        "parentId": parent_id,
        "childrenIds": [child_id],
        "role": "user",
        "content": prompt,
        "user_action": "chat",
        "files": [file_obj],
        "timestamp": msg_ts,
        "models": [model],
        "chat_type": "i2v",
        "feature_config": feature_config,
        "extra": {"meta": {"subChatType": "i2v", "size": size}},
        "sub_chat_type": "i2v",
        "parent_id": parent_id,
    }

    return {
        "stream": False,
        "version": API_VERSION,
        "incremental_output": True,
        "chat_id": chat_id,
        "chat_mode": "normal",
        "model": model,
        "parent_id": parent_id,
        "messages": [message_obj],
        "timestamp": msg_ts,
        "size": size,
    }


def build_stop_payload(chat_id: str) -> Dict[str, Any]:
    """构建停止生成请求载荷。

    Args:
        chat_id: 需要停止生成的对话 ID。

    Returns:
        停止生成请求载荷字典。
    """
    return {"chat_id": chat_id}


def build_new_chat_payload(
    model: str,
    chat_type: str = "t2t",
) -> Dict[str, Any]:
    """构建创建新对话的请求载荷。

    Args:
        model: 模型名称。
        chat_type: 聊天类型。

    Returns:
        创建对话请求载荷。
    """
    return {
        "title": "新建对话",
        "models": [model],
        "chat_mode": "local" if USE_LOCAL_MODE else "normal",
        "chat_type": chat_type,
        "timestamp": int(time.time() * 1000),
    }


def build_tts_payload(
    chat_id: str,
    response_id: str,
) -> Dict[str, Any]:
    """构建 TTS 语音合成请求载荷。

    Args:
        chat_id: 对话 ID。
        response_id: 助手消息 ID（response_id）。

    Returns:
        TTS 请求载荷字典。
    """
    return {
        "chat_id": chat_id,
        "timestamp": int(time.time()),
        "messages": [
            {
                "id": response_id,
                "role": "assistant",
                "sub_chat_type": "tts",
            }
        ],
    }


def build_replace_content_payload(
    new_content: str,
    origin_content: str,
) -> Dict[str, Any]:
    """构建替换消息内容的请求载荷。

    TTS 流程需要先将消息内容替换为目标文本，再请求 TTS。

    Args:
        new_content: 新的消息内容（目标 TTS 文本）。
        origin_content: 原始消息内容（用于 token 估算）。

    Returns:
        替换内容请求载荷字典。
    """
    return {
        "content_list": [
            {
                "content": new_content,
                "phase": "answer",
                "status": "finished",
                "extra": None,
                "role": "assistant",
                "usage": {
                    "input_tokens": max(1, len(origin_content) // 3),
                    "output_tokens": max(1, len(new_content) // 3),
                    "total_tokens": max(
                        1,
                        (len(origin_content) + len(new_content)) // 3,
                    ),
                    "prompt_tokens_details": {"cached_tokens": 0},
                },
            }
        ]
    }


# =============================================================================
# 文件对象构建（用于 Qwen API messages.files 字段）
# =============================================================================
def build_file_object(
    file_id: str,
    file_url: str,
    filename: str,
    size: int,
    content_type: str,
    user_id: str,
) -> Dict[str, Any]:
    """构建适配 Qwen API 的文件对象字典（OSS 上传后使用）。

    Args:
        file_id: 文件唯一 ID（uuid）。
        file_url: 文件 OSS URL。
        filename: 文件名。
        size: 文件大小（字节）。
        content_type: MIME 类型。
        user_id: 用户 ID。

    Returns:
        Qwen API 文件对象字典。
    """
    current_time = int(time.time() * 1000)
    item_id = str(uuid.uuid4())
    upload_task_id = str(uuid.uuid4())

    file_type = FILE_TYPE_MAPPING.get(content_type, "file")
    if content_type.startswith("image/"):
        file_class = "vision"
        show_type = "image"
    elif content_type.startswith("video/"):
        file_class = "vision"
        show_type = "video"
    elif content_type.startswith("audio/"):
        file_class = "audio"
        show_type = "audio"
    else:
        file_class = "document"
        show_type = "file"

    return {
        "type": file_type,
        "file": {
            "created_at": current_time,
            "data": {},
            "filename": filename,
            "hash": None,
            "id": file_id,
            "user_id": user_id,
            "meta": {
                "name": filename,
                "size": size,
                "content_type": content_type,
            },
            "update_at": current_time,
        },
        "id": file_id,
        "url": file_url,
        "name": filename,
        "collection_name": "",
        "progress": 0,
        "status": "uploaded",
        "greenNet": "success",
        "size": size,
        "error": "",
        "itemId": item_id,
        "file_type": content_type,
        "showType": show_type,
        "file_class": file_class,
        "uploadTaskId": upload_task_id,
    }


def _build_url_file_object(file_url: str, file_type: str = "image") -> Dict[str, Any]:
    """构建直接使用 URL 的文件对象（无需 OSS 上传）。

    用于处理 OpenAI vision 格式中的 image_url、video_url、input_audio 字段。

    Args:
        file_url: 文件 URL 或 base64 data URI。
        file_type: 文件类型（"image"、"video"、"audio"、"document"）。

    Returns:
        Qwen API 文件对象字典。
    """
    current_time = int(time.time() * 1000)
    file_id = str(uuid.uuid4())
    item_id = str(uuid.uuid4())
    upload_task_id = str(uuid.uuid4())

    # 检测是否为 base64 data URI
    is_base64 = file_url.startswith("data:")
    content_type = _infer_content_type(file_url, file_type)
    filename = _infer_filename(file_url, file_type)

    url = file_url
    if not is_base64:
        filename = os.path.basename(file_url.split("?")[0]) or filename

    # 根据文件类型设置 showType 和 file_class
    show_type, file_class = _get_type_attributes(file_type, is_base64)

    return {
        "type": file_type,
        "file": {
            "created_at": current_time,
            "data": {},
            "filename": filename,
            "hash": None,
            "id": file_id,
            "user_id": "",
            "meta": {
                "name": filename,
                "size": 0,
                "content_type": content_type,
            },
            "update_at": current_time,
        },
        "id": file_id,
        "url": url,
        "name": filename,
        "collection_name": "",
        "progress": 0,
        "status": "uploaded",
        "greenNet": "success",
        "size": 0,
        "error": "",
        "itemId": item_id,
        "file_type": content_type,
        "showType": show_type,
        "file_class": file_class,
        "uploadTaskId": upload_task_id,
    }


def _infer_content_type(file_url: str, file_type: str) -> str:
    """从 URL 或文件类型推断 MIME content type。

    Args:
        file_url: 文件 URL 或 data URI。
        file_type: 文件类型。

    Returns:
        MIME 类型字符串。
    """
    if file_url.startswith("data:"):
        header = file_url.split(",")[0] if "," in file_url else ""
        mime = header.split(":")[1].split(";")[0] if ":" in header else ""
        if mime:
            return mime

    # 从 URL 扩展名推断
    basename = os.path.basename(file_url.split("?")[0]).lower()
    ext_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mov": "video/quicktime",
        ".avi": "video/x-msvideo",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
        ".pdf": "application/pdf",
        ".txt": "text/plain",
    }
    for ext, ct in ext_map.items():
        if basename.endswith(ext):
            return ct

    # 默认值
    defaults = {
        "image": "image/jpeg",
        "video": "video/mp4",
        "audio": "audio/mpeg",
        "document": "application/octet-stream",
    }
    return defaults.get(file_type, "application/octet-stream")


def _infer_filename(file_url: str, file_type: str) -> str:
    """从 URL 或文件类型推断文件名。

    Args:
        file_url: 文件 URL。
        file_type: 文件类型。

    Returns:
        文件名。
    """
    basename = os.path.basename(file_url.split("?")[0])
    if basename:
        return basename

    defaults = {
        "image": "image.jpg",
        "video": "video.mp4",
        "audio": "audio.mp3",
        "document": "document.pdf",
    }
    return defaults.get(file_type, "file.bin")


def _get_type_attributes(file_type: str, is_base64: bool) -> tuple:
    """获取文件类型对应的 showType 和 file_class。

    Args:
        file_type: 文件类型。
        is_base64: 是否为 base64 数据。

    Returns:
        (showType, file_class) 元组。
    """
    type_map = {
        "image": ("image", "vision" if not is_base64 else "upload"),
        "video": ("video", "vision"),
        "audio": ("audio", "vision"),
        "document": ("document", "upload"),
    }
    return type_map.get(file_type, ("file", "upload"))


# =============================================================================
# OSS 签名（用于文件上传）
# =============================================================================
def build_oss_authorization(
    method: str,
    content_type: str,
    date: str,
    oss_headers: Dict[str, str],
    resource: str,
    access_key_id: str,
    access_key_secret: str,
) -> str:
    """生成 OSS V1 签名授权头。

    Args:
        method: HTTP 方法（PUT/GET 等）。
        content_type: 文件 MIME 类型。
        date: RFC1123 格式日期字符串。
        oss_headers: x-oss- 前缀的自定义头字典。
        resource: 规范化资源路径（/{bucket}/{object}）。
        access_key_id: OSS AccessKey ID。
        access_key_secret: OSS AccessKey Secret。

    Returns:
        格式为 "OSS {access_key_id}:{signature}" 的授权头值。
    """
    canonicalized = ""
    if oss_headers:
        sorted_h = sorted(oss_headers.items())
        canonicalized = (
            "\n".join("{}:{}".format(k, v) for k, v in sorted_h) + "\n"
        )
    sts = (
        "{}\n\n{}\n{}\n{}{}".format(
            method, content_type, date, canonicalized, resource
        )
    )
    sig = base64.b64encode(
        _hmac.new(
            access_key_secret.encode(),
            sts.encode(),
            hashlib.sha1,
        ).digest()
    ).decode()
    return "OSS {}:{}".format(access_key_id, sig)


# =============================================================================
# WAV 文件构建（TTS PCM 数据 -> WAV）
# =============================================================================
def build_wav_from_pcm(
    pcm_data: bytes,
    sample_rate: int = 24000,
    channels: int = 1,
    bits_per_sample: int = 16,
) -> bytes:
    """将 PCM 原始音频数据封装为 WAV 格式。

    Args:
        pcm_data: PCM 原始音频字节数据。
        sample_rate: 采样率，默认 24000 Hz。
        channels: 声道数，默认 1（单声道）。
        bits_per_sample: 每样本位深，默认 16 bit。

    Returns:
        完整的 WAV 文件字节数据。
    """
    data_size = len(pcm_data)
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,  # PCM format
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        data_size,
    )
    return header + pcm_data


def save_wav_file(
    pcm_data: bytes,
    save_dir: str = TTS_DIR,
) -> Optional[str]:
    """将 PCM 数据保存为 WAV 文件（文件I/O + 时间戳+UUID副作用）。

    注意：此函数涉及文件书写副作用。在client.py的request_tts()
    中调用，用于WAV文件持久化。

    Args:
        pcm_data: PCM 原始音频字节数据。
        save_dir: 保存目录，默认使用 TTS_DIR。

    Returns:
        保存成功则返回文件路径，失败返回 None。
    """
    try:
        wav_data = build_wav_from_pcm(pcm_data)
        Path(save_dir).mkdir(parents=True, exist_ok=True)
        ts = int(time.time() * 1000)
        uid = uuid.uuid4().hex[:8]
        filepath = Path(save_dir) / "tts_{}_{}.wav".format(ts, uid)
        filepath.write_bytes(wav_data)
        return str(filepath)
    except Exception:
        return None


def save_image_file(
    image_data: bytes,
    content_type: str = "image/png",
    save_dir: str = GENERATED_IMAGE_DIR,
) -> Optional[str]:
    """将图片字节数据保存到本地（文件I/O + 时间戳+UUID副作用）。

    注意：此函数涉及文件书写副作用。在client.py的download_image()
    中调用，用于图片持久化。

    Args:
        image_data: 图片字节数据。
        content_type: MIME 类型，用于推断扩展名。
        save_dir: 保存目录，默认使用 GENERATED_IMAGE_DIR。

    Returns:
        保存成功则返回文件路径，失败返回 None。
    """
    try:
        ext_map = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }
        ext = ext_map.get(content_type.split(";")[0].strip(), ".png")
        Path(save_dir).mkdir(parents=True, exist_ok=True)
        ts = int(time.time() * 1000)
        uid = uuid.uuid4().hex[:8]
        filepath = Path(save_dir) / "generated_{}_{}{}".format(ts, uid, ext)
        filepath.write_bytes(image_data)
        return str(filepath)
    except Exception:
        return None


def save_video_file(
    video_data: bytes,
    save_dir: str = GENERATED_VIDEO_DIR,
) -> Optional[str]:
    """将视频字节数据保存到本地（文件I/O + 时间戳+UUID副作用）。

    注意：此函数涉及文件书写副作用。在client.py的_poll_task_status()
    中易用于视频持久化。

    Args:
        video_data: 视频字节数据。
        save_dir: 保存目录，默认使用 GENERATED_VIDEO_DIR。

    Returns:
        保存成功则返回文件路径，失败返回 None。
    """
    try:
        Path(save_dir).mkdir(parents=True, exist_ok=True)
        ts = int(time.time() * 1000)
        uid = uuid.uuid4().hex[:8]
        filepath = Path(save_dir) / "video_{}_{}.mp4".format(ts, uid)
        filepath.write_bytes(video_data)
        return str(filepath)
    except Exception:
        return None


# =============================================================================
# 文件工具
# =============================================================================
def get_mime_type(filename: str) -> str:
    """根据文件名推断 MIME 类型。

    Args:
        filename: 文件名（含扩展名）。

    Returns:
        MIME 类型字符串，无法推断则返回 application/octet-stream。
    """
    ext = os.path.splitext(filename)[1].lower()
    return EXTENSION_TO_MIME.get(ext, "application/octet-stream")


def get_file_category(content_type: str) -> Tuple[str, str]:
    """获取文件分类（file_type 和 file_class）。

    Args:
        content_type: MIME 类型。

    Returns:
        (file_type, file_class) 元组。
    """
    file_type = FILE_TYPE_MAPPING.get(content_type, "file")
    if content_type.startswith("image/"):
        file_class = "vision"
    elif content_type.startswith("video/"):
        file_class = "vision"
    elif content_type.startswith("audio/"):
        file_class = "audio"
    else:
        file_class = "document"
    return file_type, file_class


def build_cdn_video_url(
    user_id: str,
    video_type: str,
    message_id: str,
    task_id: str,
    token: str,
) -> str:
    """构建视频 CDN 下载 URL。

    Args:
        user_id: 用户 ID。
        video_type: 视频类型（如 i2v）。
        message_id: 消息 ID。
        task_id: 任务 ID。
        token: Bearer 令牌（用于 key 参数）。

    Returns:
        完整的 CDN 视频 URL。
    """
    return (
        "{}/{}/{}/{}/{}.mp4?key={}".format(
            VIDEO_CDN_BASE,
            user_id,
            video_type,
            message_id,
            task_id,
            token,
        )
    )


# =============================================================================
# SSE 单行解析（无状态）
# =============================================================================
def parse_sse_event(data_str: str) -> Optional[Dict[str, Any]]:
    """解析单行 SSE data 字段为结构化事件字典。

    此函数是无状态的，仅负责将 JSON 解析为结构化字典。
    有状态的 thinking_summary 累积逻辑由 client.py 的流循环维护。

    返回字典的 type 字段枚举：
    - "answer"：正文内容增量
    - "thinking_summary"：思考摘要（有状态，含 status/extra）
    - "image_gen_tool"：图片生成工具结果（含 urls 列表）
    - "image_gen"：直接图片内容（含 content URL）
    - "video_gen"：视频生成结果（含 content URL）
    - "usage"：token 用量
    - "response_created"：响应创建事件（含 response_id）
    - "error"：服务器错误
    - "other"：其他未知 phase 内容

    Args:
        data_str: data: 前缀之后的字符串，已去除前缀和空白。

    Returns:
        结构化事件字典或 None（跳过）。
    """
    if not data_str or data_str == "[DONE]":
        return None

    try:
        data = json.loads(data_str)
    except (json.JSONDecodeError, ValueError):
        return None

    if "error" in data:
        return {"type": "error", "message": str(data["error"])}

    if "response.created" in data:
        created = data["response.created"]
        return {
            "type": "response_created",
            "response_id": created.get("response_id", ""),
        }

    usage = data.get("usage")
    choices = data.get("choices", [])

    if not choices:
        if usage:
            return {"type": "usage", "data": usage}
        return None

    delta = choices[0].get("delta", {})
    phase = delta.get("phase")
    status = delta.get("status")
    content = delta.get("content")
    extra = delta.get("extra", {})
    role = delta.get("role", "")

    result: Optional[Dict[str, Any]] = None

    if phase == "answer":
        if content and status != "finished":
            result = {"type": "answer", "content": content}

    elif phase == "thinking_summary":
        result = {
            "type": "thinking_summary",
            "status": status or "",
            "extra": extra,
        }

    elif phase == "image_gen_tool":
        if role == "function" and status == "finished":
            imgs = extra.get(
                "image_list", extra.get("tool_result", [])
            )
            urls = [
                img.get("image", "")
                for img in imgs
                if img.get("image")
            ]
            if urls:
                result = {"type": "image_gen_tool", "urls": urls}

    elif phase == "image_gen" and content:
        result = {
            "type": "image_gen",
            "content": content,
            "extra": extra,
        }

    elif phase == "video_gen" and content:
        result = {"type": "video_gen", "content": content}

    elif (
        phase is not None
        and phase != ""
        and content
        and status != "finished"
    ):
        result = {"type": "other", "content": content}

    if usage:
        if result is not None:
            result["usage"] = usage
        else:
            result = {"type": "usage", "data": usage}

    return result


# =============================================================================
# 工具函数
# =============================================================================
def hash_password(password: str) -> str:
    """SHA-256 哈希密码。

    Args:
        password: 原始密码。

    Returns:
        十六进制哈希字符串。
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


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
# SSE 单行解析门面（符合规范 parse_sse_line 签名）
# =============================================================================

def parse_sse_line(data_str: str) -> Optional[Union[str, Dict[str, Any]]]:
    """解析单行 SSE data 字段，返回标准化增量或 None。

    将底层 parse_sse_event 的结构化结果映射到规范要求的返回协议：
    - answer 增量 → str
    - thinking_summary 增量 → {"thinking": "..."}
    - usage 事件 → {"usage": {...}}
    - 其他事件 → None（跳过）

    Args:
        data_str: data: 前缀已去除的原始 SSE 数据行。

    Returns:
        str、包含 thinking/usage 键的 dict、或 None。
    """
    event = parse_sse_event(data_str)
    if event is None:
        return None

    evt_type = event.get("type", "")

    if evt_type == "answer":
        return event.get("content", "")

    if evt_type == "thinking_summary":
        extra = event.get("extra", {})
        if extra:
            titles = extra.get("summary_title", {}).get("content", [])
            thoughts = extra.get("summary_thought", {}).get("content", [])
            parts: List[str] = []
            for t, th in zip(titles, thoughts):
                if t or th:
                    parts.append("{}: {}".format(t, th) if t else str(th))
            if parts:
                return {"thinking": "\n".join(parts)}
        return None

    if evt_type == "usage":
        return {"usage": event.get("data", {})}

    return None


