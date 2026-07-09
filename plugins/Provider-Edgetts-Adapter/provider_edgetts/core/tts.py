from __future__ import annotations

"""edgetts TTS 服务。"""

import ssl
from typing import Any, Tuple, Dict

import certifi

from .constants import (
    DEFAULT_FORMAT,
    DEFAULT_PITCH,
    DEFAULT_RATE,
    DEFAULT_VOICE,
    DEFAULT_VOLUME,
    MAX_RETRIES,
    SEC_MS_GEC_VERSION,
    WSS_HOST,
    WSS_PATH_BASE,
)
from .drm import (
    build_ssml,
    build_wss_headers,
    connect_id,
    date_to_string,
    generate_sec_ms_gec,
    parse_tts_binary_frame,
    parse_tts_text_frame,
    remove_incompatible_characters,
)
from .websocket import _RawWebSocket


def do_tts(
    text: str,
    voice: str = "",
) -> bytes:
    """调用 Edge TTS 服务。

    Args:
        text: 合成文本。
        voice: 声音名称。

    Returns:
        音频字节数据。

    Raises:
        RuntimeError: 请求失败时抛出。
    """
    voice = voice or DEFAULT_VOICE
    escaped_text = remove_incompatible_characters(text)

    connection_id = connect_id()
    sec_ms_gec = generate_sec_ms_gec()
    wss_path = (
        "{}&ConnectionId={}&Sec-MS-GEC={}&Sec-MS-GEC-Version={}"
    ).format(WSS_PATH_BASE, connection_id, sec_ms_gec, SEC_MS_GEC_VERSION)

    headers = build_wss_headers()
    ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    ws = _RawWebSocket.connect(
        host=WSS_HOST,
        port=443,
        path=wss_path,
        extra_headers=headers,
        ssl_ctx=ssl_ctx,
        timeout=15.0,
    )

    try:
        ts = date_to_string()
        config_payload = (
            "X-Timestamp:{ts}\r\n"
            "Content-Type:application/json; charset=utf-8\r\n"
            "Path:speech.config\r\n"
            "X-RequestId:{rid}\r\n\r\n"
            '{{"context":{{"synthesis":{{"audio":{{'
            '"metadataoptions":{{"sentenceBoundaryEnabled":"false","wordBoundaryEnabled":"false"}},'
            '"outputFormat":"{format}"}}}}}}}}'
        ).format(ts=ts, rid=connect_id(), format=DEFAULT_FORMAT)
        ws.send_text(config_payload)

        ssml = build_ssml(voice, DEFAULT_RATE, DEFAULT_VOLUME, DEFAULT_PITCH, escaped_text)
        ssml_payload = (
            "X-RequestId:{rid}\r\n"
            "Content-Type:application/ssml+xml\r\n"
            "X-Timestamp:{ts}Z\r\n"
            "Path:ssml\r\n\r\n"
            "{ssml}"
        ).format(rid=connect_id(), ts=ts, ssml=ssml)
        ws.send_text(ssml_payload)

        audio_chunks: bytearray = bytearray()
        while True:
            opcode, payload = ws.recv_message(timeout=30.0)
            if opcode == 0x2:
                frame_headers, audio_data = parse_tts_binary_frame(payload)
                if frame_headers.get(b"Path") == b"audio" and audio_data:
                    audio_chunks.extend(audio_data)
            elif opcode == 0x1:
                frame_headers, _ = parse_tts_text_frame(payload)
                if frame_headers.get(b"Path") == b"turn.end":
                    break
            elif opcode == 0x8:
                break
        return bytes(audio_chunks)
    finally:
        ws.close()
