# -*- coding: utf-8 -*-
from __future__ import annotations

"""OpenAI 兼容路由——媒体端点 (Images, Audio, Video, Embeddings, etc.)

包含所有媒体相关的端点处理函数：
- Responses API (create_response)
- Embeddings (create_embeddings)
- Images (create_image, edit_image, create_image_variation)
- Audio (create_speech, create_transcription, create_audio_translation)
- Video (create_video)
- Moderations (create_moderation)
- Rerank (create_rerank)
"""

import time
import uuid
from typing import Any, Dict, List, Optional, Union

import aiohttp.web

from src.core.errors import NoCandidateError, ProviderError
from src.core.server import (
    clean_fncall as _clean_fncall,
)
from src.core.server import (
    get_json as _get_json,
)
from src.core.server import REGISTRY_KEY
from src.core.tools import normalize_content
from src.logger import get_logger
from src.routes.openai_helpers import (
    _err,
    _json,
    _normalize_messages,
    _not_supported,
)

__all__ = [
    "create_response",
    "create_embeddings",
    "create_image",
    "edit_image",
    "create_image_variation",
    "create_speech",
    "create_transcription",
    "create_audio_translation",
    "create_video",
    "create_moderation",
    "create_rerank",
]

logger = get_logger(__name__)



# =======================================================================
# Responses API
# =======================================================================

async def create_response(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """Responses API 端点 /v1/responses。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    from src.core import gateway

    body = await _get_json(request)
    if body is None:
        return _err(400, "Invalid JSON", "invalid_json")

    mdl = body.get("model", "")
    input_data = body.get("input", "")

    if isinstance(input_data, str):
        messages: List[Dict[str, Any]] = [{"role": "user", "content": input_data}]
    elif isinstance(input_data, list):
        messages = _normalize_messages(input_data)
    else:
        messages = [{"role": "user", "content": str(input_data)}]

    instructions = body.get("instructions")
    if instructions:
        instructions_str = normalize_content(instructions)
        if instructions_str:
            messages.insert(0, {"role": "system", "content": instructions_str})

    tools_raw = body.get("tools")
    tools: Optional[List[Dict]] = None
    if tools_raw:
        tools = [t for t in tools_raw if t.get("type") == "function"]

    cp: List[str] = []
    usage_d: Optional[Dict] = None
    try:
        async for ch in gateway.dispatch(
            registry=request.app[REGISTRY_KEY],
            messages=messages,
            model=mdl,
            stream=False,
            tools=tools,
        ):
            if isinstance(ch, str):
                cp.append(ch)
            elif isinstance(ch, dict) and "usage" in ch:
                usage_d = ch["usage"]
    except NoCandidateError as e:
        return _err(503, str(e), "no_candidate")
    except ProviderError as e:
        return _err(502, str(e), "provider_error")

    content = _clean_fncall("".join(cp))
    resp_id = "resp_{}".format(uuid.uuid4().hex[:24])

    return _json(
        {
            "id": resp_id,
            "object": "response",
            "created_at": int(time.time()),
            "model": mdl,
            "output": [
                {
                    "type": "message",
                    "id": "msg_{}".format(uuid.uuid4().hex[:16]),
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": content}],
                }
            ],
            "usage": usage_d
            or {
                "input_tokens": sum(
                    len(str(m.get("content", ""))) // 3 for m in messages
                ),
                "output_tokens": len(content) // 3,
                "total_tokens": 0,
            },
        }
    )


# =======================================================================
# Embeddings
# =======================================================================

async def create_embeddings(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """嵌入向量端点 /v1/embeddings。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    body = await _get_json(request)
    if body is None:
        return _err(400, "Invalid JSON", "invalid_json")

    model = body.get("model", "")
    registry = request.app[REGISTRY_KEY]
    cands = await registry.get_candidates(model=model, capability="embedding")
    if not cands:
        cands = await registry.get_candidates(capability="embedding")
    if not cands:
        return _not_supported("Embeddings")

    selected = await registry.selector.select(cands, 1)
    cand = selected[0] if selected else None
    if cand is None:
        return _not_supported("Embeddings")

    adapter = registry.adapter_for(cand)
    try:
        result = await adapter.create_embedding(
            cand,
            body.get("input", ""),
            body.get("model", ""),
            encoding_format=body.get("encoding_format", "float"),
        )
        return _json(result)
    except NotImplementedError:
        return _not_supported("Embeddings")
    except Exception as e:
        return _err(502, str(e), "provider_error")


# =======================================================================
# Images
# =======================================================================

async def create_image(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """图片生成端点 /v1/images/generations。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    body = await _get_json(request)
    if body is None:
        return _err(400, "Invalid JSON", "invalid_json")

    registry = request.app[REGISTRY_KEY]
    model = body.get("model", "")

    # 根据 model 参数找到支持 image_gen 的平台
    if model:
        cands = await registry.get_candidates(model)
        cand = None
        for c in cands:
            if c.image_gen:
                cand = c
                break
        if cand is None:
            return _not_supported(f"Model {model} does not support image generation")
    else:
        # 无 model 时找第一个支持 image_gen 的平台
        cand = await registry.get_capable_candidate("image_gen")
        if cand is None:
            return _not_supported("Image generation")

    adapter = registry.adapter_for(cand)
    try:
        result = await adapter.create_image(
            cand,
            body.get("prompt", ""),
            body.get("model", ""),
            **{k: v for k, v in body.items() if k not in ("prompt", "model")},
        )
        return _json(result)
    except NotImplementedError:
        return _not_supported("Image generation")
    except Exception as e:
        return _err(502, str(e), "provider_error")


async def edit_image(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """图片编辑端点 /v1/images/edits。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    registry = request.app[REGISTRY_KEY]
    cand = await registry.get_capable_candidate("image_edit")
    if cand is None:
        return _not_supported("Image editing")

    adapter = registry.adapter_for(cand)
    try:
        reader = await request.multipart()
        image_data = b""
        prompt = ""
        model = ""
        async for field in reader:
            if field.name == "image":
                image_data = await field.read()
            elif field.name == "prompt":
                prompt = (await field.read()).decode("utf-8")
            elif field.name == "model":
                model = (await field.read()).decode("utf-8")
        result = await adapter.edit_image(cand, image_data, prompt, model)
        return _json(result)
    except NotImplementedError:
        return _not_supported("Image editing")
    except Exception as e:
        return _err(502, str(e), "provider_error")


async def create_image_variation(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """图片变体端点 /v1/images/variations。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    registry = request.app[REGISTRY_KEY]
    cand = await registry.get_capable_candidate("image_variation")
    if cand is None:
        return _not_supported("Image variations")

    adapter = registry.adapter_for(cand)
    try:
        reader = await request.multipart()
        image_data = b""
        model = ""
        async for field in reader:
            if field.name == "image":
                image_data = await field.read()
            elif field.name == "model":
                model = (await field.read()).decode("utf-8")
        result = await adapter.create_image_variation(cand, image_data, model)
        return _json(result)
    except NotImplementedError:
        return _not_supported("Image variations")
    except Exception as e:
        return _err(502, str(e), "provider_error")


# =======================================================================
# Audio
# =======================================================================

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


# =======================================================================
# Video
# =======================================================================

async def create_video(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """视频生成端点 /v1/videos/generations。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    body = await _get_json(request)
    if body is None:
        return _err(400, "Invalid JSON", "invalid_json")

    registry = request.app[REGISTRY_KEY]
    cand = await registry.get_capable_candidate("video_gen")
    if cand is None:
        return _not_supported("Video generation")

    adapter = registry.adapter_for(cand)
    try:
        result = await adapter.create_video(
            cand,
            body.get("prompt", ""),
            body.get("model", ""),
            **{k: v for k, v in body.items() if k not in ("prompt", "model")},
        )
        return _json(result)
    except NotImplementedError:
        return _not_supported("Video generation")
    except Exception as e:
        return _err(502, str(e), "provider_error")


# =======================================================================
# Moderations
# =======================================================================

async def create_moderation(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """内容审核端点 /v1/moderations。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    body = await _get_json(request)
    if body is None:
        return _err(400, "Invalid JSON", "invalid_json")

    registry = request.app[REGISTRY_KEY]
    cand = await registry.get_capable_candidate("moderation")
    if cand is None:
        return _not_supported("Moderations")

    adapter = registry.adapter_for(cand)
    try:
        result = await adapter.create_moderation(
            cand, body.get("input", ""), body.get("model", "")
        )
        return _json(result)
    except NotImplementedError:
        return _not_supported("Moderations")
    except Exception as e:
        return _err(502, str(e), "provider_error")


# =======================================================================
# Rerank
# =======================================================================

async def create_rerank(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """重排序端点 /v1/rerank。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    body = await _get_json(request)
    if body is None:
        return _err(400, "Invalid JSON", "invalid_json")

    registry = request.app[REGISTRY_KEY]
    cand = await registry.get_capable_candidate("rerank")
    if cand is None:
        return _not_supported("Rerank")

    adapter = registry.adapter_for(cand)
    try:
        result = await adapter.create_rerank(
            cand,
            body.get("query", ""),
            body.get("documents", []),
            body.get("model", ""),
        )
        return _json(result)
    except NotImplementedError:
        return _not_supported("Rerank")
    except Exception as e:
        return _err(502, str(e), "provider_error")
