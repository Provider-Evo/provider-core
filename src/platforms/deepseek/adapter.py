"""DeepSeek 平台适配器。"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)
_DEEPSEEK_API_BASE = "https://api.deepseek.com/v1"


class DeepSeekAdapter:
    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self._api_base = _DEEPSEEK_API_BASE

    async def chat(self, messages: List[Dict[str, Any]], model: str = "deepseek-chat",
                   extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self._api_base}/chat/completions"
        headers = {"Content-Type": "application/json", "Authorization": self._get_auth()}
        payload = {"model": model, "messages": messages}
        if extra:
            for k in ("temperature", "max_tokens", "top_p", "tools", "tool_choice"):
                if k in extra:
                    payload[k] = extra[k]
        async with self._session.post(url, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def chat_stream(self, messages: List[Dict[str, Any]], model: str = "deepseek-chat",
                          extra: Optional[Dict[str, Any]] = None) -> AsyncIterator[Dict[str, Any]]:
        url = f"{self._api_base}/chat/completions"
        headers = {"Content-Type": "application/json", "Authorization": self._get_auth()}
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

    def _get_auth(self) -> str:
        import os
        return f"Bearer {os.environ.get('DEEPSEEK_API_KEY', '')}"
