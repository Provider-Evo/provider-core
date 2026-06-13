"""登录 / Token 校验 / 用户设置同步服务。"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Dict, Final, Optional

import aiohttp

from src.logger import get_logger
from ..accounts import Account
from .endpoints import (
    AUTH_CHECK_PATH,
    BASE_URL,
    LOGIN_BATCH,
    LOGIN_CONCURRENCY,
    SETTINGS_PATH,
    SIGNIN_PATH,
    USER_AGENT,
)
from .headers import (
    build_headers,
    build_login_headers,
)
from .password import hash_password
from .settings import DEFAULT_FULL_SETTINGS

logger = get_logger(__name__)

MAX_RETRIES: Final[int] = 3
LOGIN_TIMEOUT: Final[int] = 30
SETTINGS_TIMEOUT: Final[int] = 15
TOKEN_VALIDATE_TIMEOUT: Final[int] = 10


class AuthService:
    """登录及鉴权辅助服务。

    Args:
        session: 共享的 aiohttp 会话。
        proxy_resolver: 返回当前代理 URL 的回调。
        cookies_provider: 返回当前 Cookie 字典的回调。
        on_login_success: 单账号登录成功后的回调（典型为
            ``client._rebuild_candidates``）。
        is_closing: 返回客户端是否处于关闭中的回调。
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        proxy_resolver: Callable[[], Optional[str]],
        cookies_provider: Callable[[], Dict],
        on_login_success: Callable[[], None],
        is_closing: Callable[[], bool],
    ) -> None:
        self._session = session
        self._resolve_proxy = proxy_resolver
        self._cookies = cookies_provider
        self._on_login = on_login_success
        self._is_closing = is_closing

    # ====================================================================
    # 批量登录
    # ====================================================================
    async def login_all(self, accounts: Dict[str, Account]) -> int:
        """并发批量登录所有账号；返回成功登录的数量。"""
        sem = asyncio.Semaphore(LOGIN_CONCURRENCY)
        accounts_list = list(accounts.values())

        async def _do_one(acc: Account) -> None:
            async with sem:
                if self._is_closing():
                    return
                if not acc.is_login:
                    logger.info(
                        "账号 [%s] 已登出，尝试重新登录",
                        acc.username[:6],
                    )
                    acc.token = ""
                elif acc.token and await self.validate_token(acc):
                    return
                try:
                    await self.login(acc)
                except (
                    aiohttp.ClientError,
                    asyncio.TimeoutError,
                    RuntimeError,
                    ValueError,
                ) as exc:
                    logger.error(
                        "Qwen 登录失败 [%s***]: %s",
                        acc.username[:6],
                        exc,
                    )

        for i in range(0, len(accounts_list), LOGIN_BATCH):
            if self._is_closing():
                break
            batch = accounts_list[i : i + LOGIN_BATCH]
            await asyncio.gather(
                *[_do_one(acc) for acc in batch],
                return_exceptions=True,
            )

        logged = sum(1 for acc in accounts.values() if acc.token)
        logger.info("Qwen 登录完成: %d/%d", logged, len(accounts))
        return logged

    # ====================================================================
    # 单账号登录 / 校验
    # ====================================================================
    async def validate_token(self, acc: Account) -> bool:
        """验证账号 token 是否仍然有效。"""
        if not acc.token:
            return False
        try:
            headers = {
                "authorization": "Bearer {}".format(acc.token),
                "content-type": "application/json;charset=UTF-8",
                "source": "web",
                "user-agent": USER_AGENT,
                "origin": BASE_URL,
                "referer": "{}/".format(BASE_URL),
                "accept": "application/json",
            }
            url = "{}{}".format(BASE_URL, AUTH_CHECK_PATH)
            async with self._session.get(
                url,
                headers=headers,
                ssl=False,
                timeout=aiohttp.ClientTimeout(
                    total=TOKEN_VALIDATE_TIMEOUT
                ),
                proxy=self._resolve_proxy(),
            ) as resp:
                return resp.status == 200
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return False

    async def login(self, acc: Account) -> None:
        """登录单个账号，成功后调用 ``on_login_success`` 回调。"""
        pwd_hash = acc.password_hash or hash_password(acc.password)
        headers = build_login_headers()
        payload = {"email": acc.username, "password": pwd_hash}
        last_exc: Optional[BaseException] = None

        for attempt in range(MAX_RETRIES):
            if attempt > 0:
                await asyncio.sleep(1.0 * (2 ** (attempt - 1)))
            try:
                if await self._try_login_once(acc, headers, payload, pwd_hash):
                    return
            except (
                aiohttp.ClientError,
                asyncio.TimeoutError,
                RuntimeError,
            ) as exc:
                last_exc = exc
                continue
            # 非异常但失败时 _try_login_once 会抛 RuntimeError
        if last_exc is not None:
            raise last_exc

    async def _try_login_once(
        self,
        acc: Account,
        headers: Dict[str, str],
        payload: Dict[str, str],
        pwd_hash: str,
    ) -> bool:
        """执行单次登录请求；返回是否成功，失败则抛错。"""
        url = "{}{}".format(BASE_URL, SIGNIN_PATH)
        async with self._session.post(
            url,
            headers=headers,
            json=payload,
            ssl=False,
            timeout=aiohttp.ClientTimeout(total=LOGIN_TIMEOUT),
            proxy=self._resolve_proxy(),
        ) as resp:
            if resp.status != 200:
                err = await resp.text()
                raise RuntimeError(
                    "HTTP {}: {}".format(resp.status, err[:200])
                )
            data = await resp.json()
            token = data.get("token", "")
            if not token:
                raise RuntimeError("响应中缺少 token")
            acc.token = token
            acc.user_id = data.get("id", "")
            acc.password_hash = pwd_hash
            acc.token_expires = float(data.get("expires_at", 0))
            acc.memory_disabled = False
            acc.is_login = True
            asyncio.ensure_future(self.update_settings(acc))
            self._on_login()
            return True

    # ====================================================================
    # 用户设置
    # ====================================================================
    async def update_settings(self, acc: Account) -> None:
        """同步 "关闭记忆 / 关闭非必要工具" 等用户设置。"""
        if not acc.token or acc.memory_disabled:
            return
        headers = build_headers(acc.token, cookies=self._cookies())
        url = "{}{}".format(BASE_URL, SETTINGS_PATH)
        try:
            async with self._session.post(
                url,
                headers=headers,
                json=DEFAULT_FULL_SETTINGS,
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=SETTINGS_TIMEOUT),
                proxy=self._resolve_proxy(),
            ) as resp:
                if resp.status == 200:
                    acc.memory_disabled = True
                else:
                    err = await resp.text()
                    logger.warning(
                        "Qwen 设置同步失败 [%s***]: HTTP %d: %s",
                        acc.username[:6],
                        resp.status,
                        err[:200],
                    )
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            logger.warning(
                "Qwen 设置同步异常 [%s***]: %s",
                acc.username[:6],
                exc,
            )
