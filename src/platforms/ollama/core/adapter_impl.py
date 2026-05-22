"""Ollama 核心适配器。"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator, Dict, List, Optional

import aiohttp


class OllamaCoreAdapter:
    def __init__(self, session: aiohttp.ClientSession, base_url: str = "http://localhost:11434") -> None:
        self._session = session
        self._base_url = base_url

    async def chat(self, messages, model="llama3", extra=None):
        url = f"{self._base_url}/api/chat"
        payload = {"model": model, "messages": messages, "stream": False}
        async with self._session.post(url, json=payload) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def chat_stream(self, messages, model="llama3", extra=None):
        url = f"{self._base_url}/api/chat"
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
