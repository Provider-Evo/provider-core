from __future__ import annotations

"""Anthropic 流式 SSE 事件写入原语与文本增量状态机。"""

import json
from typing import Any, Dict, List, Optional

import aiohttp.web

from src.core.server import safe_flush as _safe_flush
from src.foundation.logger import get_logger

logger = get_logger(__name__)


async def write_event(
    resp: aiohttp.web.StreamResponse,
    event: str,
    data: Dict[str, Any],
) -> None:
    """向流式响应写入一个 Anthropic SSE 事件。

    Args:
        resp: 流式响应对象。
        event: 事件名称。
        data: 事件数据字典。
    """
    line = "event: {}\ndata: {}\n\n".format(event, json.dumps(data, ensure_ascii=False))
    try:
        await resp.write(line.encode("utf-8"))
    except (ConnectionError, OSError) as exc:
        logger.warning("SSE 事件写入失败: %s", exc)


class TextDeltaState:
    """文本增量输出状态机，处理 fncall 标签检测与安全分片输出。"""

    def __init__(
        self,
        resp: aiohttp.web.StreamResponse,
        request: aiohttp.web.Request,
        text_block_idx: int,
    ) -> None:
        """初始化文本增量状态机。

        Args:
            resp: 流式响应对象。
            request: 请求对象，用于读取日志分片钩子。
            text_block_idx: 文本 content block 的索引。
        """
        self.resp = resp
        self.request = request
        self.text_block_idx = text_block_idx
        self.platform_id = ""
        self.text_buffer = ""
        self.fncall_buffer = ""
        self.in_fncall = False

    def _log_chunk(self, safe_part: str) -> None:
        """将已输出的安全文本片段记录到请求级日志缓冲。"""
        log_chunks = self.request.get("_req_log_chunks")
        if log_chunks is not None:
            log_chunks.append(safe_part)

    async def _write_text_delta(self, text: str) -> None:
        """写出一个 text_delta 事件。"""
        await write_event(
            self.resp,
            "content_block_delta",
            {
                "type": "content_block_delta",
                "index": self.text_block_idx,
                "delta": {"type": "text_delta", "text": text},
            },
        )

    async def _try_enter_fncall(self, chunk: str) -> bool:
        """检测是否命中 fncall 触发标签，命中则切换为累积模式。

        Returns:
            是否已切换为 fncall 累积模式。
        """
        from src.core.fncall.reg import get_protocol

        proto = get_protocol(platform_id=self.platform_id)
        trigger_tags = proto.get_trigger_tags()

        tag_idx = -1
        for tag in trigger_tags:
            idx = self.text_buffer.find(tag)
            if idx != -1 and (tag_idx == -1 or idx < tag_idx):
                tag_idx = idx
        if tag_idx == -1:
            return False

        safe_part = self.text_buffer[:tag_idx]
        if safe_part:
            self._log_chunk(safe_part)
            await self._write_text_delta(safe_part)
        self.fncall_buffer = self.text_buffer[tag_idx:]
        self.text_buffer = ""
        self.in_fncall = True
        return True

    async def emit(self, chunk: str) -> None:
        """处理并输出单个文本分片。"""
        if self.in_fncall:
            self.fncall_buffer += chunk
            return

        self.text_buffer += chunk

        if await self._try_enter_fncall(chunk):
            return

        safe_part, self.text_buffer = _safe_flush(
            self.text_buffer, platform_id=self.platform_id
        )
        if safe_part:
            self._log_chunk(safe_part)
            await self._write_text_delta(safe_part)
