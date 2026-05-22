"""Qwen 核心适配器实现。"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)


class QwenCoreAdapter:
    """Qwen 核心适配器。"""

    def __init__(self, session: aiohttp.ClientSession, api_key: str = "") -> None:
        self._session = session
        self._api_key = api_key
        self._api_base = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    async def chat(
        self, messages: List[Dict[str, Any]], model: str = "qwen-turbo",
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self._api_base}/chat/completions"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self._api_key}"}
        payload = {"model": model, "messages": messages}
        if extra:
            for k in ("temperature", "max_tokens", "top_p", "tools", "tool_choice"):
                if k in extra:
                    payload[k] = extra[k]
        async with self._session.post(url, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def chat_stream(
        self, messages: List[Dict[str, Any]], model: str = "qwen-turbo",
        extra: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        url = f"{self._api_base}/chat/completions"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self._api_key}"}
        payload = {"model": model, "messages": messages, "stream": True}
        if extra:
            for k in ("temperature", "max_tokens", "top_p"):
                if k in extra:
                    payload[k] = extra[k]
        async with self._session.post(url, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            async for line in resp.content:
                line = line.decode("utf-8").strip()
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        yield json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
