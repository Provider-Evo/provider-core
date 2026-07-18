# -*- coding: utf-8 -*-
from __future__ import annotations

"""OpenAI 兼容路由——图片端点 (Images)。

包含：
- create_image    /v1/images/generations
- edit_image      /v1/images/edits
- create_image_variation  /v1/images/variations
"""

import aiohttp.web

from src.core.server import REGISTRY_KEY
from src.core.server import get_json as _get_json
from src.foundation.logger import get_logger
from src.routes.openai.chat.helpers import _err, _json, _not_supported

logger = get_logger(__name__)


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
            return _not_supported("Model {} does not support image generation".format(model))
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
