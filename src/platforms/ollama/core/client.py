"""Ollama HTTP 客户端。"""

from __future__ import annotations

import aiohttp


class OllamaClient:
    def __init__(self, session: aiohttp.ClientSession, base_url: str = "http://localhost:11434") -> None:
        self._session = session
        self._base_url = base_url

    async def chat(self, model: str, messages: list) -> dict:
        async with self._session.post(
            f"{self._base_url}/api/chat",
            json={"model": model, "messages": messages, "stream": False},
        ) as resp:
            resp.raise_for_status()
            return await resp.json()
