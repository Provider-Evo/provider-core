# -*- coding: utf-8 -*-
from __future__ import annotations

"""OpenAI 兼容路由——音频端点 (Audio)。

包含：
- create_speech       /v1/audio/speech
- create_transcription  /v1/audio/transcriptions
- create_audio_translation  /v1/audio/translations
"""

from typing import Dict, Union

import aiohttp.web

from src.core.server import REGISTRY_KEY
from src.core.server import get_json as _get_json
from src.foundation.logger import get_logger
from src.routes.openai.chat.helpers import _err, _json, _not_supported

logger = get_logger(__name__)


async def create_speech(
    request: aiohttp.web.Request,
) -> Union[aiohttp.web.Response, aiohttp.web.StreamResponse]:
    """语音合成端点 /v1/audio/speech。

    Args:
        request: 请求对象。

    Returns:
        音频响应或错误响应。
    """
    body = await _get_json(request)
    if body is None:
        return _err(400, "Invalid JSON", "invalid_json")

    registry = request.app[REGISTRY_KEY]
    cand = await registry.get_capable_candidate("audio_gen")
    if cand is None:
        return _not_supported("Text-to-speech")

    adapter = registry.adapter_for(cand)
    try:
        audio_bytes = await adapter.create_speech(
            cand,
            body.get("input", ""),
            body.get("model", "tts-1"),
            body.get("voice", "alloy"),
        )
        fmt = body.get("response_format", "mp3")
        mime_map: Dict[str, str] = {
            "mp3": "audio/mpeg",
            "opus": "audio/opus",
            "aac": "audio/aac",
            "flac": "audio/flac",
            "wav": "audio/wav",
            "pcm": "audio/pcm",
        }
        return aiohttp.web.Response(
            body=audio_bytes,
            content_type=mime_map.get(fmt, "audio/mpeg"),
        )
    except NotImplementedError:
        return _not_supported("Text-to-speech")
    except Exception as e:
        return _err(502, str(e), "provider_error")


async def create_transcription(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """语音转录端点 /v1/audio/transcriptions。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    registry = request.app[REGISTRY_KEY]
    cand = await registry.get_capable_candidate("audio_transcription")
    if cand is None:
        return _not_supported("Audio transcription")

    adapter = registry.adapter_for(cand)
    try:
        reader = await request.multipart()
        audio_data = b""
        model = "whisper-1"
        async for field in reader:
            if field.name == "file":
                audio_data = await field.read()
            elif field.name == "model":
                model = (await field.read()).decode("utf-8")
        result = await adapter.create_transcription(cand, audio_data, model)
        return _json(result)
    except NotImplementedError:
        return _not_supported("Audio transcription")
    except Exception as e:
        return _err(502, str(e), "provider_error")


async def create_audio_translation(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """语音翻译端点 /v1/audio/translations。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    registry = request.app[REGISTRY_KEY]
    cand = await registry.get_capable_candidate("audio_translation")
    if cand is None:
        return _not_supported("Audio translation")

    adapter = registry.adapter_for(cand)
    try:
        reader = await request.multipart()
        audio_data = b""
        model = "whisper-1"
        async for field in reader:
            if field.name == "file":
                audio_data = await field.read()
            elif field.name == "model":
                model = (await field.read()).decode("utf-8")
        result = await adapter.create_translation(cand, audio_data, model)
        return _json(result)
    except NotImplementedError:
        return _not_supported("Audio translation")
    except Exception as e:
        return _err(502, str(e), "provider_error")
