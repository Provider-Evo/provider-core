from __future__ import annotations

"""Stateful SSE stream consumer for Qwen chat responses."""

import asyncio
import json
import uuid
from typing import Any, AsyncGenerator, Awaitable, Callable, Dict, List, Optional, Union

import aiohttp

from .sse import parse_sse_event


class StreamHandler:
    """Consume one SSE response and emit normalized stream items."""

    def __init__(self, download_image: Callable[[str], Awaitable[Optional[str]]]) -> None:
        self._download_image = download_image
        self.last_response_id: Optional[str] = None
        self._thinking_count = 0
        self._tail = b""

    async def stream(
        self,
        resp: aiohttp.ClientResponse,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """Yield normalized items from a Qwen SSE response."""
        self.last_response_id = None
        self._thinking_count = 0
        self._tail = b""
        buffer = await resp.content.readany()
        if buffer:
            async for item in self._process_buffer(buffer):
                yield item
            buffer = self._tail
        async for raw in resp.content.iter_any():
            if not raw:
                continue
            buffer += raw
            async for item in self._process_buffer(buffer):
                yield item
            buffer = self._tail

    async def _process_buffer(
        self,
        buffer: bytes,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        lines = buffer.split(b"\n")
        self._tail = lines[-1]
        for line_bytes in lines[:-1]:
            line = line_bytes.decode("utf-8", errors="replace").strip()
            if not line or not line.startswith("data:"):
                continue
            event = parse_sse_event(line[5:].lstrip())
            if event is None:
                continue
            async for item in self._dispatch(event):
                yield item

    async def _dispatch(
        self,
        event: Dict[str, Any],
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        event_type = event.get("type", "")
        if event_type == "error":
            raise RuntimeError(f"Qwen server error: {event.get('message', '')}")
        if event_type == "response_created":
            self.last_response_id = event.get("response_id")
        elif event_type == "answer":
            text = self._strip_tags(event.get("content", ""))
            if text:
                yield text
        elif event_type == "thinking":
            text = self._strip_tags(event.get("content", ""))
            if text:
                yield {"thinking": text}
        elif event_type == "thinking_summary":
            for piece in self._iter_thinking_pieces(event):
                yield {"thinking": piece}
        elif event_type == "image_gen_tool":
            calls = await asyncio.gather(
                *[self._build_single_image_call(url) for url in event.get("urls", [])]
            )
            if calls:
                yield {"tool_calls": calls}
        elif event_type == "image_gen":
            content = event.get("content", "")
            if content:
                yield {"tool_calls": [await self._build_single_image_call(content)]}
        elif event_type == "video_gen":
            content = event.get("content", "")
            if content:
                yield {"tool_calls": [self._wrap_tool_call("qwen.video_gen", {"url": content})]}
        elif event_type == "usage":
            yield {"usage": event.get("data", {})}
        elif event_type == "other":
            content = self._strip_tags(event.get("content", ""))
            if content:
                yield content
        if event.get("usage") and event_type != "usage":
            yield {"usage": event["usage"]}

    def _iter_thinking_pieces(self, event: Dict[str, Any]) -> List[str]:
        if event.get("status") != "typing":
            return []
        extra = event.get("extra", {})
        titles = extra.get("summary_title", {}).get("content", [])
        thoughts = extra.get("summary_thought", {}).get("content", [])
        total = max(len(titles), len(thoughts))
        pieces: List[str] = []
        for index in range(self._thinking_count, total):
            title = titles[index] if index < len(titles) else ""
            thought = thoughts[index] if index < len(thoughts) else ""
            pieces.append(f"{title}: {thought}" if title else thought)
        self._thinking_count = total
        return pieces

    async def _build_single_image_call(self, url: str) -> Dict[str, Any]:
        local_path = await self._download_image(url)
        arguments: Dict[str, Any] = {"url": url}
        if local_path:
            arguments["local_path"] = local_path
        return self._wrap_tool_call("qwen.image_gen", arguments)

    @staticmethod
    def _strip_tags(content: str) -> str:
        return content.replace("<think>", "").replace("</think>", "")

    @staticmethod
    def _wrap_tool_call(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": f"call_{uuid.uuid4().hex[:12]}",
            "type": "function",
            "function": {
                "name": name,
                "arguments": json.dumps(arguments, ensure_ascii=False),
            },
        }
