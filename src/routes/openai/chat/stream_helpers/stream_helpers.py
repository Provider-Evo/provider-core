# -*- coding: utf-8 -*-
from __future__ import annotations

"""OpenAI Chat Completions 流式处理 — SSE 编码与错误/参数构造辅助函数。

从 stream.py 抽出的模块级独立辅助函数，供 stream_chat 使用。
"""

import json
from typing import Any, Dict, List, Optional

import aiohttp.web

from src.core.server import REGISTRY_KEY
from src.foundation.logger import get_logger
from src.routes.openai.chat.helpers import _sl

logger = get_logger(__name__)

_SSE_HEADERS = {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _sse_chunk(
    cid: str,
    ct: int,
    mdl: str,
    delta: Dict[str, Any],
    *,
    finish_reason: Optional[str] = None,
    usage: Optional[Dict] = None,
) -> bytes:
    payload: Dict[str, Any] = {
        "id": cid,
        "object": "chat.completion.chunk",
        "created": ct,
        "model": mdl,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }
    if usage is not None:
        payload["choices"] = []
        payload["usage"] = usage
    return "data: {}\n\n".format(json.dumps(payload, ensure_ascii=False)).encode("utf-8")


def _build_error_payload(err: Exception) -> bytes:
    """构造流式错误 SSE 数据块。从 stream_chat 异常分支抽出以控制行数。"""
    from src.core.utils.errors import ModerationError

    if isinstance(err, ModerationError):
        err_code = "content_policy_violation"
        err_type = "invalid_request_error"
    else:
        err_code = err.error_type if hasattr(err, "error_type") else "internal_error"
        err_type = "server_error"
    err_data = json.dumps(
        {
            "error": {
                "message": str(err),
                "type": err_type,
                "code": err_code,
            }
        },
        ensure_ascii=False,
    )
    return "data: {}\n\n".format(err_data).encode("utf-8")


async def _handle_dispatch_exception(
    e: Exception,
    resp: aiohttp.web.StreamResponse,
) -> aiohttp.web.StreamResponse:
    """处理 gateway.dispatch 流式过程中抛出的异常，写回错误 SSE 块。

    从 stream_chat 的 except Exception 分支抽出，保持主函数在行数上限内。
    """
    from src.core.utils.errors import ModerationError
    from src.core.utils.errors.biz import NetworkError

    if isinstance(e, ModerationError):
        err = e
    elif isinstance(e, aiohttp.ClientConnectorError):
        err = NetworkError("连接失败: {}".format(e), original=e)
        logger.error("流式连接错误: %s", e, exc_info=True)
    else:
        err = e
        logger.error("流式错误: %s", e, exc_info=True)

    try:
        await resp.write(_build_error_payload(err))
    except Exception as exc:
        logger.debug("流式错误信息写回失败，可能连接已关闭: %s", exc)
    return resp


def _build_dispatch_kwargs(
    request: aiohttp.web.Request,
    body: Dict[str, Any],
    messages: List[Dict[str, Any]],
    mdl: str,
    tools_raw: Any,
    extra: Dict[str, Any],
    upload_files: Any,
    proto_override: str,
) -> Dict[str, Any]:
    """构造 gateway.dispatch 的调用参数。从 stream_chat 抽出以控制行数。"""
    return {
        "registry": request.app[REGISTRY_KEY],
        "messages": messages,
        "model": mdl,
        "stream": True,
        "tools": tools_raw,
        "thinking": bool(extra.get("thinking")),
        "search": bool(extra.get("search")),
        "temperature": body.get("temperature"),
        "top_p": body.get("top_p"),
        "max_tokens": body.get("max_tokens"),
        "stop": _sl(body.get("stop")),
        "upload_files": upload_files if upload_files else None,
        "protocol_id": proto_override,
        "tool_choice": body.get("tool_choice"),
        "platform": extra.get("platform", ""),
    }
