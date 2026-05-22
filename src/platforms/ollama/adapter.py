"""Ollama 平台适配器。"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)
_OLLAMA_API_BASE = "http://localhost:11434"


class OllamaAdapter:
    def __init__(self, session: aiohttp.ClientSession, base_url: str = _OLLAMA_API_BASE) -> None:
        self._session = session
        self._api_base = base_url

    async def chat(
        self, messages: List[Dict[str, Any]], model: str = "llama3",
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self._api_base}/api/chat"
        payload = {"model": model, "messages": messages, "stream": False}
        async with self._session.post(url, json=payload) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def chat_stream(
        self, messages: List[Dict[str, Any]], model: str = "llama3",
        extra: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        url = f"{self._api_base}/api/chat"
        payload = {"model": model, "messages": messages, "stream": True}
        async with self._session.post(url, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.content:
                line = line.decode("utf-8").strip()
                if line:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue
