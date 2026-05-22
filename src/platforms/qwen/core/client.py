"""Qwen 客户端封装。"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)


class QwenClient:
    """Qwen HTTP 客户端。"""

    def __init__(self, session: aiohttp.ClientSession, api_key: str = "") -> None:
        self._session = session
        self._api_key = api_key
        self._base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    async def request(
        self, endpoint: str, payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        url = f"{self._base_url}/{endpoint.lstrip('/')}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        async with self._session.post(url, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def stream_request(
        self, endpoint: str, payload: Dict[str, Any],
    ) -> AsyncIterator[str]:
        url = f"{self._base_url}/{endpoint.lstrip('/')}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        async with self._session.post(url, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            async for line in resp.content:
                yield line.decode("utf-8")
