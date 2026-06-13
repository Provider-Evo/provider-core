from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp

from src.core.candidate import Candidate, make_id
from .constants import BASE_URL, CHAT_PATH
from .headers import build_headers
from .models import MODELS
from .payloads import build_payload
from .sse import parse_sse_line

logger = logging.getLogger(__name__)
MAX_RETRIES = 3


class PerplexityClient:
    """Perplexity HTTP client.

    Coordinates HTTP requests to the Perplexity API, including retry logic
    and SSE streaming.
    """

    def __init__(self) -> None:
        self._session: Optional[aiohttp.ClientSession] = None

    async def init(self, session: aiohttp.ClientSession) -> None:
        """Initialize the client with an aiohttp session.

        Args:
            session: The shared aiohttp ClientSession.
        """
        self._session = session
        logger.info("perplexity 初始化完成")

    async def candidates(self) -> List[Candidate]:
        """Return the list of available candidates.

        Returns:
            A list with one public candidate (no API key required).
        """
        return [
            Candidate(
                id=make_id("perplexity", "public"),
                platform="perplexity",
                resource_id="public",
                models=MODELS,
                meta={},
                chat=True,
                tools=False,
                vision=False,
                thinking=True,
                search=True,
            )
        ]

    async def ensure_candidates(self, count: int) -> int:
        """Ensure at least `count` candidates are available.

        Args:
            count: Minimum number of candidates expected.

        Returns:
            The actual number of candidates (always 1 for Perplexity).
        """
        return 1

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
        """Execute a chat completion request with retries.

        Args:
            candidate: The selected candidate.
            messages: The conversation message list.
            model: The model name.
            stream: Whether to stream the response.
            thinking: Whether to enable thinking mode.
            search: Whether to enable search.
            **kw: Additional keyword arguments (unused).

        Yields:
            Text chunks or usage dicts from the SSE stream.
        """
        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                await asyncio.sleep(1.0 * (2 ** (attempt - 1)))
            try:
                async for chunk in self._do_request(
                    candidate, messages, model, stream
                ):
                    yield chunk
                return
            except Exception as e:
                last_exc = e
                logger.warning(
                    "perplexity 重试 %d/%d: %s", attempt + 1, MAX_RETRIES, e
                )
        if last_exc is not None:
            raise last_exc

    async def _do_request(
        self,
        candidate: Candidate,
        messages: List[Dict[str, Any]],
        model: str,
        stream: bool,  # noqa: ARG002
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """Execute a single HTTP request and yield SSE events.

        Args:
            candidate: The selected candidate.
            messages: The conversation message list.
            model: The model name.
            stream: Whether to stream (unused, always streams).

        Yields:
            Parsed SSE data items.

        Raises:
            RuntimeError: If the session is not initialized.
            Exception: On HTTP error responses.
        """
        if self._session is None:
            raise RuntimeError("session not initialized")

        prompt = self._extract_prompt(messages)

        request_id = str(uuid.uuid4())
        referer = f"{BASE_URL}/"
        headers = build_headers("", referer=referer, request_id=request_id)

        convo: Dict[str, Any] = {
            "frontend_uid": str(uuid.uuid4()),
            "frontend_context_uuid": str(uuid.uuid4()),
            "last_backend_uuid": None,
            "read_write_token": None,
            "thread_url_slug": None,
        }

        payload = build_payload(prompt, model, followup=False, convo=convo)
        url = f"{BASE_URL}{CHAT_PATH}"

        async with self._session.post(
            url,
            json=payload,
            headers=headers,
            ssl=False,
            timeout=aiohttp.ClientTimeout(connect=10, total=300),
        ) as resp:
            if resp.status != 200:
                raise Exception(
                    f"perplexity HTTP {resp.status}: {await resp.text()}"
                )

            async for line in resp.content:
                if not line:
                    continue
                text = line.decode("utf-8", errors="replace").strip()
                if not text or not text.startswith("data:"):
                    continue
                data_str = text[5:].strip()
                if data_str == "[DONE]":
                    break
                parsed = parse_sse_line(data_str)
                if parsed is not None:
                    yield parsed

    @staticmethod
    def _extract_prompt(messages: List[Dict[str, Any]]) -> str:
        """Extract the last user message as the prompt.

        Args:
            messages: The conversation message list.

        Returns:
            The extracted prompt string.
        """
        for m in reversed(messages):
            if m.get("role") == "user":
                content = m.get("content")
                if isinstance(content, list):
                    return "\n".join(
                        item.get("text", "")
                        for item in content
                        if isinstance(item, dict)
                    )
                return str(content)
        return ""

    async def close(self) -> None:
        """Close the client (no-op for Perplexity)."""
        return None
