"""媒体文件本地持久化工具（图片 / 视频 / TTS WAV）。

封装 PCM→WAV 头构建以及统一的 "时间戳 + 短 UUID" 文件命名规则。
"""

from __future__ import annotations

import struct
import time
import uuid
from pathlib import Path
from typing import Final, Optional

from src.logger import get_logger
from .endpoints import (
    GENERATED_IMAGE_DIR,
    GENERATED_VIDEO_DIR,
    TTS_DIR,
)

logger = get_logger(__name__)

# 图片 MIME 到扩展名的映射
_IMAGE_EXT_MAP: Final[dict] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def build_wav_from_pcm(
    pcm_data: bytes,
    sample_rate: int = 24000,
    channels: int = 1,
    bits_per_sample: int = 16,
) -> bytes:
    """将 PCM 原始音频数据封装为 WAV 格式。

    Args:
        pcm_data: PCM 原始音频字节。
        sample_rate: 采样率（默认 24000 Hz）。
        channels: 声道数（默认 1）。
        bits_per_sample: 每样本位深（默认 16）。

    Returns:
        完整 WAV 文件字节数据。
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


def _make_path(save_dir: str, prefix: str, ext: str) -> Path:
    """生成 ``{prefix}_{ms}_{uuid8}{ext}`` 形式的目标路径。"""
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    ts = int(time.time() * 1000)
    uid = uuid.uuid4().hex[:8]
    return Path(save_dir) / "{}_{}_{}{}".format(prefix, ts, uid, ext)


def save_wav_file(
    pcm_data: bytes,
    save_dir: str = TTS_DIR,
) -> Optional[str]:
    """将 PCM 数据封装为 WAV 并保存到本地。

    Args:
        pcm_data: PCM 原始音频字节。
        save_dir: 保存目录。

    Returns:
        成功时返回文件路径；失败返回 ``None``。
    """
    try:
        wav_data = build_wav_from_pcm(pcm_data)
        filepath = _make_path(save_dir, "tts", ".wav")
        filepath.write_bytes(wav_data)
        return str(filepath)
    except (OSError, ValueError) as exc:
        logger.warning("WAV 保存失败: %s", exc)
        return None


def save_image_file(
    image_data: bytes,
    content_type: str = "image/png",
    save_dir: str = GENERATED_IMAGE_DIR,
) -> Optional[str]:
    """将图片字节数据保存到本地。

    Args:
        image_data: 图片字节数据。
        content_type: MIME 类型，用于推断扩展名。
        save_dir: 保存目录。

    Returns:
        成功时返回文件路径；失败返回 ``None``。
    """
    try:
        ext = _IMAGE_EXT_MAP.get(content_type.split(";")[0].strip(), ".png")
        filepath = _make_path(save_dir, "generated", ext)
        filepath.write_bytes(image_data)
        return str(filepath)
    except (OSError, ValueError) as exc:
        logger.warning("图片保存失败: %s", exc)
        return None


def save_video_file(
    video_data: bytes,
    save_dir: str = GENERATED_VIDEO_DIR,
) -> Optional[str]:
    """将视频字节数据保存到本地。

    Args:
        video_data: 视频字节数据。
        save_dir: 保存目录。

    Returns:
        成功时返回文件路径；失败返回 ``None``。
    """
    try:
        filepath = _make_path(save_dir, "video", ".mp4")
        filepath.write_bytes(video_data)
        return str(filepath)
    except (OSError, ValueError) as exc:
        logger.warning("视频保存失败: %s", exc)
        return None
