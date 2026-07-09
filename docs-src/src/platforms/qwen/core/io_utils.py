from __future__ import annotations

# Qwen I/O utilities (file I/O, OSS signing, audio/video saving)

import base64
import hashlib
import hmac as _hmac
import os
import struct
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Final, Optional, Tuple

from src.platforms.qwen.core.endpoints import (
    GENERATED_IMAGE_DIR,
    GENERATED_VIDEO_DIR,
    TTS_DIR,
    VIDEO_CDN_BASE,
)
from src.platforms.qwen.core.mimes import EXTENSION_TO_MIME, FILE_TYPE_MAPPING


# =============================================================================
# OSS signature (for file upload)
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
# WAV file construction (TTS PCM data -> WAV)
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
# File tools
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
