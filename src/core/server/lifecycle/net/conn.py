
from __future__ import annotations

import ssl
from typing import Optional

import aiohttp

from src.foundation.config import get_config

__all__ = [
    "close_shared_connector",
    "make_connector",
    "get_ssl_context",
    "make_client_timeout",
]

# Module-level cache so multiple calls within the same process return the
# same connector (avoids accidental duplicate pools).
_connector: Optional[aiohttp.TCPConnector] = None

# SSL 上下文缓存，避免重复创建
_ssl_context: Optional[ssl.SSLContext] = None


def get_ssl_context() -> ssl.SSLContext:
    """获取或创建 SSL 上下文（复用）。

    Returns:
        配置为不验证主机名的 SSLContext 实例。
    """
    global _ssl_context
    if _ssl_context is not None:
        return _ssl_context

    _ssl_context = ssl.create_default_context()
    _ssl_context.check_hostname = False
    _ssl_context.verify_mode = ssl.CERT_NONE
    return _ssl_context


def make_client_timeout() -> aiohttp.ClientTimeout:
    """创建基于配置的 ClientTimeout。

    支持分级超时策略：
    - connect_timeout: 连接建立超时
    - sock_read: 读取超时
    - sock_connect: 连接超时
    - total: 总超时

    Returns:
        配置好的 ClientTimeout 实例。
    """
    cfg = get_config()
    pool = cfg.http_pool

    return aiohttp.ClientTimeout(
        total=pool.total_timeout,
        connect=pool.connect_timeout,
        sock_read=pool.read_timeout,
        sock_connect=pool.connect_timeout,
    )


def make_connector() -> aiohttp.TCPConnector:
    """创建或返回缓存的 aiohttp.TCPConnector。

    从 config.toml 的 [http_pool] 部分读取配置。

    优化点：
    1. 复用 SSL 上下文，减少内存分配
    2. 支持可配置的连接池参数
    3. 启用连接清理，防止内存泄漏
    4. 分级超时策略

    Returns:
        共享的 TCPConnector 实例。"""
    global _connector
    if _connector is not None and not _connector.closed:
        return _connector

    cfg = get_config()
    pool = cfg.http_pool

    # 复用 SSL 上下文
    ctx = get_ssl_context()

    _connector = aiohttp.TCPConnector(
        ssl=ctx,
        limit=pool.limit,
        limit_per_host=pool.limit_per_host,
        keepalive_timeout=pool.keepalive_timeout,
        force_close=False,
        enable_cleanup_closed=True,
    )
    return _connector


async def close_shared_connector() -> None:
    """关闭进程级共享 TCPConnector，避免关停后 asyncio.run 等待连接清理。"""
    global _connector, _ssl_context
    conn = _connector
    _connector = None
    _ssl_context = None
    if conn is None or conn.closed:
        return
    await conn.close()
