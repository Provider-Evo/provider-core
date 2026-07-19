# -*- coding: utf-8 -*-
from __future__ import annotations

"""OpenAI 兼容路由——媒体端点 (Embeddings, Moderations, Rerank)。

图片端点见 uploads_images.py，音频端点见 uploads_audio.py。
Responses API 见 responses_api.py，Video 端点见 videos.py。
"""

import aiohttp.web

from src.core.server import REGISTRY_KEY
from src.core.server import get_json as _get_json
from src.foundation.logger import get_logger
from src.routes.openai.chat.helpers import _err, _json, _not_supported
from src.routes.openai.media.uploads_audio import (
    create_audio_translation,
    create_speech,
    create_transcription,
)
from src.routes.openai.media.uploads_images import (
    create_image,
    create_image_variation,
    edit_image,
)
from src.routes.openai.media.videos import create_video  # noqa: F401
from src.routes.openai.resp_api import create_response  # noqa: F401

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

# Responses API 已迁移至 responses_api.py；图片/音频已迁移至 uploads_images/audio.py；此处保留 re-export。


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
