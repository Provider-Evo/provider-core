# -*- coding: utf-8 -*-
from __future__ import annotations

"""OpenAI Chat Completions 流式处理 — 流式响应状态机 _StreamState。

从 stream.py 抽出，避免单个文件超过行数上限。
"""

import json
import uuid
from typing import Any, Dict, List, Optional

import aiohttp.web

from src.core.server import safe_flush as _safe_flush
from src.core.utils.compat.observability import get_observability_services
from src.foundation.logger import get_logger
from src.routes.openai.chat.stream_helpers.stream_helpers import _sse_chunk
from src.webui.data.services.logs.request_log import request_broker

logger = get_logger(__name__)


class _StreamState:
    """流式响应过程中的可变状态与增量写回逻辑。

    从 stream_chat 中抽出，避免单个函数超过行数上限。持有的字段与原函数体内
    局部变量/闭包一一对应，行为保持不变。
    """

    def __init__(
        self,
        resp: aiohttp.web.StreamResponse,
        cid: str,
        ct: int,
        mdl: str,
        tools_raw: Any,
        fncall_enabled: bool,
        proto_override: str,
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
        self.fncall_enabled = fncall_enabled
        self.proto_override = proto_override
        self.log_chunks = log_chunks
        self.log_id = log_id
        self.live_chunks = live_chunks
        self.observability = observability

        self.ctok = 0
        self.has_tc = False
        self.usage_d: Optional[Dict] = None
        self.buffer = ""
        self.fncall_buffer = ""
        self.in_fncall = False
        self.tool_calls_data: List[Dict[str, Any]] = []
        self.platform_id: str = ""
        self.proto: Any = None
        self.init_chunk_sent = False

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

    def resolve_proto(self) -> Any:
        from src.core.fncall.reg import get_protocol

        self.proto = get_protocol(
            protocol_id=self.proto_override, platform_id=self.platform_id
        )
        return self.proto

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
        for idx, tc in enumerate(tc_list):
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

    def _detect_tag_idx(self) -> int:
        """在 buffer 中定位函数调用触发标签的位置，未命中返回 -1。"""
        trigger_tags = self.proto.get_trigger_tags()
        tag_idx = -1
        detect_start = (
            self.proto.detect_start if hasattr(self.proto, "detect_start") else None
        )
        if callable(detect_start):
            try:
                found, pos = detect_start(self.buffer)
                if found:
                    tag_idx = pos
            except Exception:
                pass
        if tag_idx == -1:
            for tag in trigger_tags:
                idx = self.buffer.find(tag)
                if idx != -1 and (tag_idx == -1 or idx < tag_idx):
                    tag_idx = idx
        return tag_idx

    async def _process_fncall_str_chunk(self) -> None:
        """在启用函数调用检测时处理文本增量。从 process_str_chunk 抽出。"""
        if self.proto is None:
            self.resolve_proto()
        tag_idx = self._detect_tag_idx()

        if tag_idx != -1:
            safe_part = self.buffer[:tag_idx]
            if safe_part:
                await self.emit_content(safe_part)
            self.fncall_buffer = self.buffer[tag_idx:]
            self.buffer = ""
            self.in_fncall = True
            return

        safe_part, self.buffer = _safe_flush(
            self.buffer,
            platform_id=self.platform_id,
            protocol_id=self.proto_override,
            protocol=self.proto,
        )
        await self.emit_content(safe_part)

    async def process_str_chunk(self, ch: str) -> None:
        self.ctok += 1

        if not self.fncall_enabled:
            await self.emit_content(ch)
            return

        if self.in_fncall:
            self.fncall_buffer += ch
            return

        self.buffer += ch
        await self._process_fncall_str_chunk()

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

    async def process_dict_chunk(self, ch: Dict[str, Any]) -> None:
        if "_meta" in ch:
            new_platform = ch["_meta"].get("platform", "")
            if new_platform and new_platform != self.platform_id:
                self.platform_id = new_platform
                self.proto = None
                if self.platform_id:
                    self.resp._platform = self.platform_id
        elif "thinking" in ch:
            await self._process_thinking_chunk(ch["thinking"])
        elif "tool_calls" in ch:
            self.tool_calls_data = ch["tool_calls"]
            self.has_tc = True
        elif "usage" in ch:
            self.usage_d = ch["usage"]

    async def finalize(self) -> None:
        """流结束后的收尾：补发残留内容、函数调用与结束帧。"""
        if self.buffer and not self.in_fncall:
            await self.emit_content(self.buffer)

        if self.in_fncall and self.fncall_buffer and not self.tool_calls_data:
            if self.proto is None:
                self.resolve_proto()
            _, self.tool_calls_data = self.proto.parse(
                self.fncall_buffer, self.tools_raw
            )
            if self.tool_calls_data:
                self.has_tc = True

        if self.tool_calls_data:
            await self.send_init()
            await self.send_tc_incremental(self.tool_calls_data)
        else:
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
    """构造并初始化 _StreamState。从 stream_chat 抽出以控制行数。"""
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
        fncall_enabled=bool(tools_raw),
        proto_override="",
        log_chunks=log_chunks,
        log_id=log_id,
        live_chunks=live_chunks,
        observability=observability,
    )
