# -*- coding: utf-8 -*-
from __future__ import annotations

"""SSE 流处理器 — 参考 mock.py 的 SSEStreamProcessor 实现初始注释保活。"""

import asyncio
import random
import time
from dataclasses import dataclass

import aiohttp.web

from src.foundation.logger import get_logger

__all__ = [
    "SSEStreamConfig",
    "SSEStreamProcessor",
]

logger = get_logger(__name__)


@dataclass
class SSEStreamConfig:
    """SSE 流配置。"""

    sse_comment_marker: str = "PROVIDER"
    sse_comment_interval: float = 0.1
    initial_comments_wait_min: float = 0.2
    initial_comments_wait_max: float = 0.8

    @classmethod
    def default(cls) -> SSEStreamConfig:
        return cls()


class SSEStreamProcessor:
    """在首个数据块到达前发送 SSE 注释，保持连接活跃。"""

    def __init__(self, config: SSEStreamConfig | None = None) -> None:
        self.config = config or SSEStreamConfig.default()
        self._comment_count = 0
        self._is_stopping = False

    def stop(self) -> None:
        """停止初始注释阶段。"""
        self._is_stopping = True

    async def run_initial_comments(self, resp: aiohttp.web.StreamResponse) -> None:
        """在等待上游首个 chunk 期间按固定间隔发送 SSE 注释。"""
        self._comment_count = 0
        self._is_stopping = False
        wait_time = random.uniform(
            self.config.initial_comments_wait_min,
            self.config.initial_comments_wait_max,
        )
        logger.debug(
            "SSE initial comments: wait={:.3f}s interval={:.3f}s marker={}",
            wait_time,
            self.config.sse_comment_interval,
            self.config.sse_comment_marker,
        )
        start_time = time.time()
        while not self._is_stopping and time.time() - start_time < wait_time:
            await self._send_comment(resp)
            await asyncio.sleep(self.config.sse_comment_interval)
        logger.debug("SSE initial comments done, sent {}", self._comment_count)

    async def _send_comment(self, resp: aiohttp.web.StreamResponse) -> None:
        line = ": {} PROCESSING\n\n".format(self.config.sse_comment_marker)
        await resp.write(line.encode("utf-8"))
        self._comment_count += 1
