# -*- coding: utf-8 -*-
from __future__ import annotations

"""OpenAI Chat Completions 流式处理 — SSE 写回状态。

fncall 解析在 dispatch 层经 FncallStreamParser 完成；此处只负责 SSE 格式化写回。
"""

import json
import uuid
from typing import Any, Dict, List, Optional

import aiohttp.web

from src.core.utils.compat.tools import normalize_tool_calls
from src.core.utils.compat.observability import get_observability_services
from src.foundation.logger import get_logger
from src.routes.openai.chat.stream_helpers.stream_helpers import _sse_chunk
from src.webui.data.services.logs.request_log import request_broker

logger = get_logger(__name__)


class _StreamState:
    """流式响应过程中的 mutable 状态与 SSE 写回。"""

    def __init__(
        self,
        resp: aiohttp.web.StreamResponse,
        cid: str,
        ct: int,
        mdl: str,
        tools_raw: Any,
        log_chunks: Optional[list],
        log_id: Optional[str],
        live_chunks: bool,
        observability: Any,
    ) -> None:
        self.resp = resp
        self.cid = cid
        self.ct = ct
        self.mdl = mdl
        self.tools_raw = tools_raw
        self.log_chunks = log_chunks
        self.log_id = log_id
        self.live_chunks = live_chunks
        self.observability = observability

        self.ctok = 0
        self.has_tc = False
        self.usage_d: Optional[Dict] = None
        self.tool_calls_data: List[Dict[str, Any]] = []
        self.platform_id: str = ""
        self.init_chunk_sent = False
        self._streamed_tc_count = 0

    async def send_init(self) -> None:
        if self.init_chunk_sent:
            return
        self.init_chunk_sent = True
        delta = (
            {"role": "assistant", "content": None}
            if self.tools_raw
            else {"role": "assistant", "content": ""}
        )
        await self.resp.write(_sse_chunk(self.cid, self.ct, self.mdl, delta))

    async def emit_content(self, safe_part: str) -> None:
        if not safe_part:
            return
        if self.log_chunks is not None:
            self.log_chunks.append(safe_part)
        if self.live_chunks and self.log_id and self.observability is not None:
            try:
                self.observability.push_request_event(
                    {"type": "request_chunk", "id": self.log_id, "delta": safe_part},
                )
            except Exception:
                pass
        await self.send_init()
        await self.resp.write(
            _sse_chunk(self.cid, self.ct, self.mdl, {"content": safe_part})
        )

    async def _send_tc_fragment(self, idx: int, arg_fragment: str) -> None:
        await self.resp.write(
            _sse_chunk(
                self.cid,
                self.ct,
                self.mdl,
                {
                    "tool_calls": [
                        {"index": idx, "function": {"arguments": arg_fragment}}
                    ]
                },
            )
        )

    async def _send_tc_header(self, idx: int, tc: Dict[str, Any], name: str) -> None:
        await self.resp.write(
            _sse_chunk(
                self.cid,
                self.ct,
                self.mdl,
                {
                    "tool_calls": [
                        {
                            "index": idx,
                            "id": tc.get("id", "call_{}".format(uuid.uuid4().hex[:24])),
                            "type": "function",
                            "function": {"name": name, "arguments": ""},
                        }
                    ]
                },
            )
        )

    async def send_tc_incremental(self, tc_list: List[Dict[str, Any]]) -> None:
        chunk_size = 20
        for idx, tc in enumerate(tc_list, start=self._streamed_tc_count):
            fn = tc.get("function", {})
            name = fn.get("name", "")
            args = fn.get("arguments", "")
            if isinstance(args, dict):
                args = json.dumps(args, ensure_ascii=False)

            await self._send_tc_header(idx, tc, name)

            for start in range(0, max(len(args), 1), chunk_size):
                frag = args[start : start + chunk_size]
                if not frag and start > 0:
                    break
                await self._send_tc_fragment(idx, frag)
        self._streamed_tc_count += len(tc_list)

    async def process_str_chunk(self, ch: str) -> None:
        self.ctok += 1
        await self.emit_content(ch)

    async def _process_thinking_chunk(self, thinking_text: str) -> None:
        await self.send_init()
        await self.resp.write(
            _sse_chunk(
                self.cid,
                self.ct,
                self.mdl,
                {
                    "content": "",
                    "reasoning": thinking_text,
                    "reasoning_details": [
                        {
                            "type": "reasoning.text",
                            "text": thinking_text,
                            "format": "unknown",
                            "index": 0,
                        }
                    ],
                },
            )
        )

    async def _append_tool_calls(self, tc_list: List[Dict[str, Any]]) -> None:
        if not tc_list:
            return
        normalized = normalize_tool_calls(tc_list, self.tools_raw)
        if not normalized:
            return
        self.tool_calls_data.extend(normalized)
        self.has_tc = True
        await self.send_init()
        await self.send_tc_incremental(normalized)

    async def process_dict_chunk(self, ch: Dict[str, Any]) -> None:
        if "_meta" in ch:
            new_platform = ch["_meta"].get("platform", "")
            if new_platform and new_platform != self.platform_id:
                self.platform_id = new_platform
                if self.platform_id:
                    self.resp._platform = self.platform_id
        elif "thinking" in ch:
            await self._process_thinking_chunk(ch["thinking"])
        elif "tool_calls" in ch:
            await self._append_tool_calls(ch["tool_calls"])
        elif "usage" in ch:
            self.usage_d = ch["usage"]

    async def finalize(self) -> None:
        """流结束后的收尾：补发结束帧。"""
        if not self.init_chunk_sent:
            await self.send_init()

        fr = "tool_calls" if self.has_tc else "stop"
        u = self.usage_d or {
            "prompt_tokens": 0,
            "completion_tokens": self.ctok,
            "total_tokens": self.ctok,
        }

        try:
            await self.resp.write(
                _sse_chunk(self.cid, self.ct, self.mdl, {}, finish_reason=fr)
            )
            await self.resp.write(_sse_chunk(self.cid, self.ct, self.mdl, {}, usage=u))
            await self.resp.write(b"data: [DONE]\n\n")
        except Exception as exc:
            logger.debug("流式结束块写回失败，可能连接已关闭: %s", exc)


async def build_stream_state(
    request: aiohttp.web.Request,
    resp: aiohttp.web.StreamResponse,
    cid: str,
    ct: int,
    mdl: str,
    tools_raw: Any,
) -> _StreamState:
    """构造并初始化 _StreamState。"""
    log_chunks: Optional[list] = request.get("_req_log_chunks")
    log_id: Optional[str] = request.get("_req_log_id")
    live_chunks = request_broker.has_listeners
    observability = get_observability_services() if live_chunks else None
    return _StreamState(
        resp=resp,
        cid=cid,
        ct=ct,
        mdl=mdl,
        tools_raw=tools_raw,
        log_chunks=log_chunks,
        log_id=log_id,
        live_chunks=live_chunks,
        observability=observability,
    )
