from __future__ import annotations

"""TTS service for the current Qwen web protocol."""

import base64
import json
from typing import Any, Awaitable, Callable, Dict, List, Optional

import aiohttp

from .endpoints import BASE_URL, TTS_DIR, TTS_PATH, TTS_TIMEOUT
from .headers import build_headers
from .payloads import build_replace_content_payload, build_tts_payload
from .storage import save_wav_file


class TtsService:
    """Encapsulate the end-to-end TTS flow."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        proxy_resolver: Callable[[], Optional[str]],
        cookies_provider: Callable[[], dict],
        fingerprint_provider: Callable[[], str],
        create_chat: Callable[[str, str, str], Awaitable[str]],
        get_response_id: Callable[[str, str, str], Awaitable[tuple[Optional[str], str]]],
        schedule_cleanup: Callable[[str, str], None],
    ) -> None:
        self._session = session
        self._resolve_proxy = proxy_resolver
        self._cookies = cookies_provider
        self._fingerprint = fingerprint_provider
        self._create_chat = create_chat
        self._get_response_id = get_response_id
        self._schedule_cleanup = schedule_cleanup

    async def synthesize(
        self,
        text: str,
        token: str,
        model: str = "qwen3-max",
        save_dir: str = TTS_DIR,
    ) -> Optional[str]:
        """Run the full placeholder-replace-synthesize TTS flow."""
        try:
            chat_id = await self._create_chat(token, model, "t2t")
            response_id, origin_text = await self._get_response_id(chat_id, token, model)
            if not response_id:
                return None
            if not await self.replace_message_content(chat_id, response_id, text, origin_text.strip(), token):
                return None
            return await self.request_tts(chat_id, response_id, token, save_dir)
        finally:
            if "chat_id" in locals():
                self._schedule_cleanup(chat_id, token)

    async def replace_message_content(
        self,
        chat_id: str,
        response_id: str,
        new_content: str,
        origin_content: str,
        token: str,
    ) -> bool:
        """Replace an assistant message before TTS synthesis."""
        async with self._session.post(
            f"{BASE_URL}/api/v2/chats/{chat_id}/messages/{response_id}",
            json=build_replace_content_payload(new_content, origin_content),
            headers=build_headers(token, chat_id=chat_id, cookies=self._cookies()),
            ssl=False,
            timeout=aiohttp.ClientTimeout(total=30),
            proxy=self._resolve_proxy(),
        ) as response:
            return response.status == 200

    async def request_tts(
        self,
        chat_id: str,
        response_id: str,
        token: str,
        save_dir: str = TTS_DIR,
    ) -> Optional[str]:
        """Request TTS audio and persist the decoded WAV file."""
        headers = build_headers(
            token,
            chat_id=chat_id,
            include_sse=True,
            fingerprint=self._fingerprint(),
            cookies=self._cookies(),
        )
        headers["Accept"] = "*/*"
        chunks: List[str] = []
        async with self._session.post(
            f"{BASE_URL}{TTS_PATH}?chat_id={chat_id}",
            json=build_tts_payload(chat_id, response_id),
            headers=headers,
            ssl=False,
            timeout=aiohttp.ClientTimeout(total=TTS_TIMEOUT),
            proxy=self._resolve_proxy(),
        ) as response:
            if response.status != 200:
                return None
            buffer = b""
            async for raw in response.content.iter_any():
                if not raw:
                    continue
                buffer += raw
                lines = buffer.split(b"\n")
                buffer = lines[-1]
                for line_bytes in lines[:-1]:
                    line = line_bytes.decode("utf-8", errors="replace").strip()
                    if not line.startswith("data:"):
                        continue
                    data_str = line[5:].lstrip()
                    if not data_str or data_str == "[DONE]":
                        continue
                    payload = json.loads(data_str)
                    choices = payload.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    tts_fragment = delta.get("tts")
                    if tts_fragment:
                        chunks.append(tts_fragment)
                    if delta.get("status") == "finished":
                        break
        if not chunks:
            return None
        combined = "".join(chunks)
        padding = (-len(combined)) % 4
        if padding:
            combined += "=" * padding
        return save_wav_file(base64.b64decode(combined), save_dir)
