from __future__ import annotations

# src/platforms/deepseek/core/hif.py
"""DeepSeek HIF 服务令牌管理"""

import asyncio
import time
from typing import Any, Optional, Tuple

from src.foundation.logger import get_logger

import aiohttp

from src.platforms.deepseek.core.constants import (
    HIF_DLIQ_URL,
    HIF_LEIM_URL,
    HIF_REFRESH_INTERVAL,
)
from src.platforms.deepseek.core.headers import build_basic_headers

logger = get_logger(__name__)


async def fetch_hif_tokens(
    session: Any,
) -> Tuple[str, str, float]:
    """并发获取两个 HIF 服务令牌。

    Args:
        session: aiohttp.ClientSession 实例。

    Returns:
        (x_hif_leim, x_hif_dliq, expire_at) 三元组。
        失败时对应字段返回空字符串，expire_at 返回当前时间。
    """
    headers = build_basic_headers()

    async def _get(url: str) -> str:
        try:
            async with session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
                ssl=False,
            ) as resp:
                if resp.status != 200:
                    logger.warning("HIF 令牌获取失败 %s: HTTP %d", url, resp.status)
                    return ""
                data = await resp.json()
                code = data.get("code", data.get("data", {}).get("code", -1))
                # 兼容两种响应格式
                biz = (
                    data.get("data", {}).get("biz_data", {})
                    if "data" in data
                    else data
                )
                val = biz.get("value", "")
                return str(val) if val else ""
        except Exception as exc:
            logger.warning("HIF 令牌获取异常 %s: %s", url, exc)
            return ""

    leim, dliq = await asyncio.gather(_get(HIF_LEIM_URL), _get(HIF_DLIQ_URL))
    expire_at = time.time() + HIF_REFRESH_INTERVAL
    logger.debug("HIF 令牌刷新完成 leim=%s... dliq=%s...", leim[:8], dliq[:8])
    return leim, dliq, expire_at


class HifTokenManager:
    """HIF 令牌自动刷新管理器（每个账号独立实例）。"""

    def __init__(self) -> None:
        """初始化管理器。"""
        self._leim: str = ""
        self._dliq: str = ""
        self._expire_at: float = 0.0
        self._session: Optional[Any] = None

    def bind_session(self, session: Any) -> None:
        """绑定 aiohttp Session。

        Args:
            session: aiohttp.ClientSession 实例。
        """
        self._session = session

    def is_expired(self) -> bool:
        """判断令牌是否已过期。

        Returns:
            是否已过期。
        """
        return time.time() >= self._expire_at - 60

    async def ensure_valid(self) -> Tuple[str, str]:
        """确保令牌有效，过期自动刷新。

        Returns:
            (x_hif_leim, x_hif_dliq) 二元组。
        """
        if self.is_expired() and self._session is not None:
            self._leim, self._dliq, self._expire_at = await fetch_hif_tokens(
                self._session
            )
        return self._leim, self._dliq

    @property
    def leim(self) -> str:
        """当前 x-hif-leim 令牌。"""
        return self._leim

    @property
    def dliq(self) -> str:
        """当前 x-hif-dliq 令牌。"""
        return self._dliq
