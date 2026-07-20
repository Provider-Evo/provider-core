"""Worker 端口占用检测与绑定重试。"""

from __future__ import annotations

import asyncio

import aiohttp

from src.core.dispatch.engine.registry import Registry
from src.core.server import ensure_port_available
from src.core.server.lifecycle.app.app_host import AppHost
from src.foundation.logger import get_logger

logger = get_logger(__name__)


async def handle_port_occupied(
    port: int,
    force_kill: bool,
    attempt: int,
    max_retries: int,
    delay: float,
    session: aiohttp.ClientSession,
    registry: Registry,
) -> bool:
    """处理端口被占用；返回 True 表示应继续重试，False/异常表示放弃。"""
    port_result = ensure_port_available(port, force_kill)
    if not (port_result.occupied and not port_result.released):
        return True
    if attempt < max_retries - 1:
        logger.warning(
            "端口 %d 被占用 (PIDs: %s)，%s，等待 %.1f 秒后重试 (%d/%d)...",
            port,
            port_result.pids,
            "已尝试强制终止" if force_kill else "未强制终止",
            delay,
            attempt + 1,
            max_retries,
        )
        await asyncio.sleep(delay)
        return False
    logger.error(
        "端口 %d 被占用 (PIDs: %s)，重试 %d 次后仍无法释放，退出",
        port,
        port_result.pids,
        max_retries,
    )
    await session.close()
    await registry.close()
    raise SystemExit(1)


async def try_start_app_host(
    app_host: AppHost,
    port: int,
    attempt: int,
    max_retries: int,
    delay: float,
    session: aiohttp.ClientSession,
    registry: Registry,
) -> bool:
    """尝试启动 AppHost；绑定失败时按重试次数决定是否放弃。"""
    try:
        await app_host.start()
        return True
    except OSError as exc:
        await app_host.shutdown()
        if attempt < max_retries - 1:
            logger.warning(
                "端口 %d 绑定失败 (%s)，等待 %.1f 秒后重试 (%d/%d)...",
                port,
                exc,
                delay,
                attempt + 1,
                max_retries,
            )
            await asyncio.sleep(delay)
            return False
        logger.error(
            "端口 %d 绑定失败，重试 %d 次后仍无法绑定，退出: %s", port, max_retries, exc
        )
        await session.close()
        await registry.close()
        raise SystemExit(1)


async def bind_port_with_retry(
    cfg: object,
    app_host: AppHost,
    session: aiohttp.ClientSession,
    registry: Registry,
) -> None:
    """带重试的端口绑定；重试耗尽后关闭 session/registry 并退出进程。"""
    port = cfg.server.port
    force_kill = cfg.server.startup_force_kill_port
    max_port_retries = 8
    port_retry_delay = 1.0

    for port_attempt in range(max_port_retries):
        port_free = await handle_port_occupied(
            port,
            force_kill,
            port_attempt,
            max_port_retries,
            port_retry_delay,
            session,
            registry,
        )
        if not port_free:
            port_retry_delay = min(port_retry_delay * 1.5, 8.0)
            continue

        started = await try_start_app_host(
            app_host,
            port,
            port_attempt,
            max_port_retries,
            port_retry_delay,
            session,
            registry,
        )
        if started:
            return
        port_retry_delay = min(port_retry_delay * 1.5, 8.0)

    await session.close()
    await registry.close()
    raise SystemExit(1)
