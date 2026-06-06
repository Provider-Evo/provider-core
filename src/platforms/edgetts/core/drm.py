from __future__ import annotations

"""edgetts DRM 相关函数。"""

import hashlib
import secrets
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Tuple

from .constants import (
    TRUSTED_CLIENT_TOKEN,
    WIN_EPOCH,
    S_TO_NS,
    WSS_HANDSHAKE_HEADERS,
)


def generate_sec_ms_gec() -> str:
    """生成 Sec-MS-GEC 值。

    Returns:
        SHA256 哈希字符串。
    """
    ticks = datetime.now(timezone.utc).timestamp()
    ticks += WIN_EPOCH
    ticks -= ticks % 300
    ticks *= S_TO_NS / 100
    return hashlib.sha256("{}{}".format(ticks, TRUSTED_CLIENT_TOKEN).encode("ascii")).hexdigest().upper()


def connect_id() -> str:
    """生成连接 ID。

    Returns:
        UUID 十六进制字符串。
    """
    return uuid.uuid4().hex


def date_to_string() -> str:
    """生成日期字符串。

    Returns:
        格式化的日期字符串。
    """
    return time.strftime(
        "%a %b %d %Y %H:%M:%S GMT+0000 (Coordinated Universal Time)",
        time.gmtime(),
    )


def remove_incompatible_characters(text: str) -> str:
    """移除不兼容字符。

    Args:
        text: 原始文本。

    Returns:
        清理后的文本。
    """
    chars = list(text)
    for idx, ch in enumerate(chars):
        code = ord(ch)
        if (0 <= code <= 8) or (11 <= code <= 12) or (14 <= code <= 31):
            chars[idx] = " "
    return "".join(chars)


def build_ssml(voice: str, rate: str, volume: str, pitch: str, text: str) -> str:
    """构建 SSML 字符串。

    Args:
        voice: 声音名称。
        rate: 语速。
        volume: 音量。
        pitch: 音调。
        text: 合成文本。

    Returns:
        SSML 字符串。
    """
    return (
        "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'>"
        "<voice name='{voice}'><prosody pitch='{pitch}' rate='{rate}' volume='{volume}'>"
        "{text}</prosody></voice></speak>"
    ).format(voice=voice, pitch=pitch, rate=rate, volume=volume, text=text)


def parse_tts_text_frame(data: bytes) -> Tuple[Dict[bytes, bytes], bytes]:
    """解析 TTS 文本帧。

    Args:
        data: 原始字节数据。

    Returns:
        元组 (头部字典, 载荷数据)。
    """
    sep = data.find(b"\r\n\r\n")
    if sep < 0:
        return {}, b""
    headers: Dict[bytes, bytes] = {}
    for line in data[:sep].split(b"\r\n"):
        if b":" not in line:
            continue
        key, value = line.split(b":", 1)
        headers[key.strip()] = value.strip()
    return headers, data[sep + 4 :]


def parse_tts_binary_frame(data: bytes) -> Tuple[Dict[bytes, bytes], bytes]:
    """解析 TTS 二进制帧。

    Args:
        data: 原始字节数据。

    Returns:
        元组 (头部字典, 载荷数据)。
    """
    if len(data) < 2:
        return {}, b""
    header_length = int.from_bytes(data[:2], "big")
    if 2 + header_length > len(data):
        return {}, b""
    headers: Dict[bytes, bytes] = {}
    for line in data[2 : 2 + header_length].split(b"\r\n"):
        if b":" not in line:
            continue
        key, value = line.split(b":", 1)
        headers[key.strip()] = value.strip()
    return headers, data[2 + header_length :]


def build_wss_headers() -> Dict[str, str]:
    """构建 WebSocket 握手头部。

    Returns:
        请求头字典。
    """
    h = dict(WSS_HANDSHAKE_HEADERS)
    h["Cookie"] = "muid={};".format(secrets.token_hex(16).upper())
    return h
