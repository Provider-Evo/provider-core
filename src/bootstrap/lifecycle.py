from __future__ import annotations

"""应用生命周期钩子 — 通过 observability 访问 WebUI 实现。"""

import asyncio
from typing import Any

import aiohttp.web

from src.core.observability import observability_from_app
from src.logger import get_logger

logger = get_logger(__name__)


async def on_startup(application: aiohttp.web.Application) -> None:
    """启动：持久化后台任务、日志 sink、终端恢复。"""
    obs = observability_from_app(application)
    logger.debug("aiohttp.web application started")
    try:
        obs.start_stats_persist()
    except Exception as exc:
        logger.warning("启动统计持久化失败: %s", exc, exc_info=True)
    try:
        obs.start_request_persist()
    except Exception as exc:
        logger.warning("启动请求日志持久化失败: %s", exc, exc_info=True)
    try:
        obs.set_log_broker_loop(asyncio.get_running_loop())
        obs.setup_loguru_sink()
    except Exception as exc:
        logger.warning("配置日志 WebSocket sink 失败: %s", exc, exc_info=True)
    try:
        await obs.recover_terminal_sessions(application.get("registry"))
    except Exception as exc:
        logger.warning("恢复终端会话失败: %s", exc, exc_info=True)


async def on_cleanup(application: aiohttp.web.Application) -> None:
    """清理：保存统计与终端状态。"""
    obs = observability_from_app(application)
    logger.info("aiohttp.web application cleaning up")
    try:
        obs.save_stats()
    except Exception as exc:
        logger.warning("保存统计失败: %s", exc, exc_info=True)
    try:
        obs.save_terminal_states()
    except Exception as exc:
        logger.warning("保存终端状态失败: %s", exc, exc_info=True)
