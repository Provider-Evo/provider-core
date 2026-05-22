from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

import aiohttp.web

from src.core.http import get_json, json_response

__all__ = ["setup_routes"]
logger = logging.getLogger(__name__)


async def _handle_chat(request: aiohttp.web.Request) -> aiohttp.web.Response:
    body = await get_json(request)
    if body is None:
        return json_response(
            {"error": {"message": "Invalid JSON", "type": "invalid_request_error"}}, status=400)

    model = body.get("model", "qwen-turbo")
    messages = body.get("messages", [])
    stream = body.get("stream", False)
    session: aiohttp.ClientSession = request.app["session"]

    if stream:
        return await _handle_stream(request, session, model, messages, body)
    return await _handle_non_stream(session, model, messages, body)


async def _handle_non_stream(
    session: aiohttp.ClientSession, model: str, messages: List[Dict[str, Any]], body: Dict[str, Any],
) -> aiohttp.web.Response:
    platform = _select_platform(model)
    if platform == "deepseek":
        from src.platforms.deepseek.adapter import DeepSeekAdapter
        adapter = DeepSeekAdapter(session)
    else:
        from src.platforms.qwen.adapter import QwenAdapter
        adapter = QwenAdapter(session)
    try:
        result = await adapter.chat(messages, model, body)
        return json_response(result)
    except Exception as e:
        logger.error("聊天请求失败: %s", e)
        return json_response({"error": {"message": str(e), "type": "api_error"}}, status=500)


async def _handle_stream(
    request: aiohttp.web.Request, session: aiohttp.ClientSession,
    model: str, messages: List[Dict[str, Any]], body: Dict[str, Any],
) -> aiohttp.web.Response:
    platform = _select_platform(model)
    if platform == "deepseek":
        from src.platforms.deepseek.adapter import DeepSeekAdapter
        adapter = DeepSeekAdapter(session)
    else:
        from src.platforms.qwen.adapter import QwenAdapter
        adapter = QwenAdapter(session)

    response = aiohttp.web.StreamResponse(headers={
        "Content-Type": "text/event-stream", "Cache-Control": "no-cache",
        "Connection": "keep-alive", "X-Accel-Buffering": "no",
    })
    await response.prepare(request)
    try:
        async for chunk in adapter.chat_stream(messages, model, body):
            data = f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            await response.write(data.encode("utf-8"))
    except Exception as e:
        logger.error("流式请求失败: %s", e)
    finally:
        await response.write(b"data: [DONE]\n\n")
    return response


def _select_platform(model: str) -> str:
    if model.lower().startswith(("deepseek", "deepseek-")):
        return "deepseek"
    return "qwen"


def setup_routes(app: aiohttp.web.Application) -> None:
    app.router.add_route("POST", "/v1/chat/completions", _handle_chat)
    app.router.add_route("POST", "/chat/completions", _handle_chat)
