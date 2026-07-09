from __future__ import annotations

"""Platform-level adapter wrapper for the Qwen client."""

import asyncio
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp

try:
    from src.core.dispatch.candidate import Candidate
except ModuleNotFoundError:
    from .runtime import Candidate

try:
    from provider_sdk.extensions.platform.adapter import PlatformAdapter
except ModuleNotFoundError:
    from .runtime import PlatformAdapter

from .client import QwenClient


class QwenAdapter(PlatformAdapter):
    """Expose the Qwen client through the platform adapter interface.

    媒体能力通过 ``QwenClient`` 提供，路由层可按需调用
    :class:`~src.platforms.capabilities.ImageCapable` /
    :class:`~src.platforms.capabilities.AudioCapable` 约定。
    """

    @property
    def name(self) -> str:
        return "qwen"

    def __init__(self) -> None:
        self._client = QwenClient()
        self._session: Optional[aiohttp.ClientSession] = None
        self._init_lock = asyncio.Lock()
        self._initialized = False

    async def init(self, session: aiohttp.ClientSession) -> None:
        """Initialize the adapter (session parameter ignored; manages own session)."""
        await self.ensure_initialized()

    async def close(self) -> None:
        """Shut down the client and the shared HTTP session."""
        await self.shutdown()

    async def ensure_initialized(self) -> None:
        """Initialize the underlying HTTP client once."""
        if self._initialized:
            return
        async with self._init_lock:
            if self._initialized:
                return
            from src.core.server.infra.connector import make_connector

            timeout = aiohttp.ClientTimeout(total=None, connect=20, sock_connect=20, sock_read=None)
            connector = make_connector()
            session = aiohttp.ClientSession(timeout=timeout, connector=connector)
            try:
                await self._client.init_immediate(session)
            except Exception:
                if not session.closed:
                    await session.close()
                raise
            self._session = session
            asyncio.create_task(self._client.background_setup())
            self._initialized = True

    async def shutdown(self) -> None:
        """Shut down the client and the shared HTTP session."""
        if not self._initialized:
            return
        await self._client.close()
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._initialized = False

    async def candidates(self) -> List[Candidate]:
        """Return available account-backed candidates."""
        await self.ensure_initialized()
        return await self._client.candidates()

    async def ensure_candidates(self, count: int) -> int:
        """Return the current candidate count."""
        await self.ensure_initialized()
        return await self._client.ensure_candidates(count)

    async def complete(
        self,
        candidate: Candidate,
        messages: List[Dict[str, Any]],
        model: str,
        stream: bool,
        *,
        thinking: bool = False,
        search: bool = False,
        **kw: Any,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """Proxy chat completion calls to the underlying Qwen client."""
        await self.ensure_initialized()
        async for chunk in self._client.complete(
            candidate, messages, model, stream, thinking=thinking, search=search, **kw,
        ):
            yield chunk

    async def stop(self, candidate: Candidate) -> bool:
        """Stop the active generation for the given candidate."""
        await self.ensure_initialized()
        return await self._client.stop_candidate_generation(candidate)

    @property
    def supported_models(self) -> List[str]:
        """返回当前支持的模型列表。

        Returns:
            模型 ID 列表。
        """
        return self._client.get_models()

    async def get_models(self) -> List[str]:
        """Return the current model list."""
        await self.ensure_initialized()
        return self._client.get_models()

    async def set_proxy_enabled(self, enabled: bool) -> None:
        """Force-enable or disable proxy usage."""
        await self.ensure_initialized()
        self._client.set_proxy_enabled(enabled)

    async def is_proxy_enabled(self) -> bool:
        """Return whether proxy use is currently forced on."""
        await self.ensure_initialized()
        return self._client.is_proxy_enabled()

    async def refresh_models(self) -> None:
        """Trigger a remote model refresh."""
        await self.ensure_initialized()
        await self._client.refresh_models()

    async def generate_video(
        self,
        prompt: str,
        image_url: str,
        token: str,
        user_id: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Expose the client image-to-video helper."""
        await self.ensure_initialized()
        return await self._client.generate_video(prompt, image_url, token, user_id, **kwargs)

    async def synthesize_tts(
        self,
        text: str,
        token: str,
        **kwargs: Any,
    ) -> Optional[str]:
        """Expose the client TTS helper."""
        await self.ensure_initialized()
        return await self._client.synthesize_tts(text, token, **kwargs)

    def get_config(self) -> Dict[str, Any]:
        """Return a lightweight adapter config view."""
        return {
            "platform": "qwen",
            "models": self._client.get_models(),
        }
