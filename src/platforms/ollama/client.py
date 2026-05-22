"""Ollama HTTP 客户端。"""

from __future__ import annotations

import aiohttp


class OllamaClient:
    def __init__(self, session: aiohttp.ClientSession, base_url: str = "http://localhost:11434") -> None:
        self._session = session
        self._base_url = base_url

    async def list_models(self) -> list:
        async with self._session.get(f"{self._base_url}/api/tags") as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data.get("models", [])
