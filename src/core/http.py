"""共享 HTTP 工具函数。"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import aiohttp.web

logger = logging.getLogger(__name__)


def clean_fncall(text: str) -> str:
    """清理函数调用标签。"""
    text = text.replace("<function_calls>", "").replace("</function_calls>", "")
    text = text.replace("<tools>", "").replace("</tools>", "")
    return text.strip()


async def safe_flush(writer: Any) -> None:
    """安全刷新写入流。"""
    try:
        await writer.drain()
    except (ConnectionError, BrokenPipeError) as e:
        logger.warning("连接已关闭: %s", e)


async def get_json(request: aiohttp.web.Request) -> Optional[dict]:
    """安全解析 JSON 请求体。"""
    try:
        return await request.json()
    except json.JSONDecodeError:
        return None


def json_response(data: Any, status: int = 200, headers: Optional[dict] = None) -> aiohttp.web.Response:
    """构建 JSON 响应。"""
    body = json.dumps(data, ensure_ascii=False)
    resp_headers = {"Content-Type": "application/json"}
    if headers:
        resp_headers.update(headers)
    return aiohttp.web.Response(body=body.encode("utf-8"), status=status, headers=resp_headers)
