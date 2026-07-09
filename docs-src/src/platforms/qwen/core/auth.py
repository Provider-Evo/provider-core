"""Authentication mixin for QwenClient.

Provides login, token validation, settings sync, cookie refresh,
and background login polling.
"""

from __future__ import annotations

import asyncio
import random
import time
from typing import Any, Dict, List, Optional

import aiohttp

from src.logger import get_logger
from src.platforms.qwen.accounts import Account
from src.platforms.qwen.core.shared import (
    AUTH_CHECK_PATH,
    BASE_URL,
    COOKIE_REFRESH_INTERVAL,
    DEFAULT_FULL_SETTINGS,
    INITIAL_LOGIN_MAX,
    LOGIN_BATCH_SIZE,
    LOGIN_POLL_INTERVAL,
    LOGIN_POOL_SIZE,
    LOGIN_SELECT_MAX,
    LOGIN_SELECT_MIN,
    SETTINGS_PATH,
    SIGNIN_PATH,
    TOKEN_EXPIRY_MARGIN,
    USER_AGENT,
    build_headers,
    build_login_headers,
    generate_cookies,
    generate_fingerprint,
    hash_password,
)

logger = get_logger(__name__)

MAX_RETRIES: int = 3
LOGIN_TIMEOUT: int = 30
SETTINGS_TIMEOUT: int = 15


class AuthMixin:
    """Mixin providing login, token management, and cookie refresh.

    Expects the composed class to provide:
    - ``_session``: aiohttp.ClientSession
    - ``_account_states``: Dict[str, Account]
    - ``_closing``: bool
    - ``_cookies``: Dict[str, Any]
    - ``_fp``: str (fingerprint)
    - ``_get_proxy_kwarg()``: method returning Optional[str]
    - ``_rebuild_candidates()``: method
    - ``_save_persist()``: method
    - ``_load_task_timers()`` / ``_save_task_timers()``: methods
    - ``_log_queued_relogin()`` / ``_log_login_failure()``: methods from LogsMixin
    """

    # =====================================================================
    # Initial login pass
    # =====================================================================

    async def _initial_login_pass(self) -> None:
        """Startup quick login batch.

        Validates tokens restored from persistence and re-logs-in
        expired accounts.  Processes at most INITIAL_LOGIN_MAX accounts
        sequentially (no concurrency).
        """
        now = time.time()
        need_login: List[Account] = []

        for acc in self._account_states.values():
            if acc.is_login and acc.token:
                if not await self._validate_token(acc):
                    self._log_queued_relogin(acc.username[:6])
                    acc.is_login = False
                    acc.token = ""
                    need_login.append(acc)
            elif not acc.is_login:
                need_login.append(acc)

        # Oldest / most-expired first
        need_login.sort(key=lambda a: a.token_expires)

        batch = need_login[:INITIAL_LOGIN_MAX]

        if batch:
            logger.debug(
                "Qwen 初始登录: %d 个账号需要登录，本次处理 %d 个",
                len(need_login), len(batch),
            )
            _network_breaker_hit = False
            for acc in batch:
                if self._closing or _network_breaker_hit:
                    break
                try:
                    await self._login_and_configure(acc)
                except Exception as e:
                    err_str = str(e)
                    self._log_login_failure(acc.username[:6], err_str)
                    if not _network_breaker_hit and (
                        "Cannot connect" in err_str
                        or "远程计算机拒绝" in err_str
                        or "连接" in err_str
                    ):
                        _network_breaker_hit = True
                        logger.info(
                            "Qwen 登录端点不可达，跳过本批次剩余账号"
                        )

            self._rebuild_candidates()
            self._save_persist()

        logged = sum(
            1 for acc in self._account_states.values() if acc.is_login
        )
        logger.debug(
            "Qwen 初始登录完成: %d/%d 账号已登录",
            logged, len(self._account_states),
        )

    # =====================================================================
    # Background login poll loop
    # =====================================================================

    async def _login_poll_loop(self) -> None:
        """Background login polling loop.

        Every LOGIN_POLL_INTERVAL seconds:
        1. Smart-select a batch of accounts needing re-login.
        2. Login each account sequentially (with settings sync).
        3. Rebuild candidates and persist after the batch.

        Task timer persistence: on first iteration, restores the last
        run timestamp from disk so restarts don't reset the timer.
        """
        timers = self._load_task_timers()
        last_run = timers.get("login_poll", 0)
        remaining = LOGIN_POLL_INTERVAL - (time.time() - last_run)

        while not self._closing:
            sleep_time = remaining if remaining > 0 else LOGIN_POLL_INTERVAL
            remaining = -1  # only effective on first iteration

            await asyncio.sleep(sleep_time)
            if self._closing:
                break

            try:
                batch = self._select_login_batch()
                if batch:
                    logger.debug(
                        "Qwen 登录轮询: 选中 %d 个账号", len(batch),
                    )
                    _network_breaker_hit = False
                    for acc in batch:
                        if self._closing or _network_breaker_hit:
                            break
                        try:
                            await self._login_and_configure(acc)
                        except Exception as e:
                            err_str = str(e)
                            self._log_login_failure(acc.username[:6], err_str)
                            if not _network_breaker_hit and (
                                "Cannot connect" in err_str
                                or "远程计算机拒绝" in err_str
                                or "连接" in err_str
                            ):
                                _network_breaker_hit = True
                                logger.info(
                                    "Qwen 登录端点不可达，跳过本批次剩余账号"
                                )

                    self._rebuild_candidates()
                    self._save_persist()

                    success = sum(1 for a in batch if a.is_login)
                    logger.debug(
                        "Qwen 登录轮询完成: %d/%d 成功",
                        success, len(batch),
                    )
            except Exception as e:
                logger.warning("Qwen 登录轮询异常: %s", e)

            timers["login_poll"] = time.time()
            self._save_task_timers(timers)

    # =====================================================================
    # Smart batch selection
    # =====================================================================

    def _select_login_batch(self) -> List[Account]:
        """Smart-select accounts for this login round.

        Algorithm:
        1. Filter un-logged-in or soon-to-expire accounts.
        2. Sort by token_expires ascending (oldest first).
        3. Take top LOGIN_POOL_SIZE as candidate pool.
        4. Randomly pick LOGIN_SELECT_MIN..LOGIN_SELECT_MAX from pool.
        5. Take first LOGIN_BATCH_SIZE of the selection as the batch.
        6. Shuffle the batch.
        """
        now = time.time()
        not_logged_in: List[Account] = []

        for acc in self._account_states.values():
            if not acc.is_login:
                not_logged_in.append(acc)
            elif acc.token and acc.token_expires > 0:
                remaining = acc.token_expires - now
                if remaining < TOKEN_EXPIRY_MARGIN:
                    not_logged_in.append(acc)

        if not not_logged_in:
            return []

        not_logged_in.sort(key=lambda a: a.token_expires)

        pool = not_logged_in[:LOGIN_POOL_SIZE]
        select_count = random.randint(LOGIN_SELECT_MIN, LOGIN_SELECT_MAX)
        selected = pool[:select_count]
        random.shuffle(selected)
        batch = selected[:LOGIN_BATCH_SIZE]

        for acc in batch:
            if acc.is_login and acc.token:
                acc.is_login = False
                acc.token = ""

        return batch

    # =====================================================================
    # Login + configure single account
    # =====================================================================

    async def _login_and_configure(self, acc: Account) -> None:
        """Login a single account and sync settings.

        1. HTTP login via ``_login()``.
        2. On success, ``await _update_settings()`` (not fire-and-forget).
        3. Settings sync sets ``memory_disabled = True``.

        Caller is responsible for ``_rebuild_candidates()`` and
        ``_save_persist()`` after the whole batch.
        """
        await self._login(acc)

        try:
            await self._update_settings(acc)
        except Exception as e:
            logger.warning(
                "Qwen 设置同步异常 [%s***]: %s", acc.username[:6], e,
            )

    # =====================================================================
    # Token validation
    # =====================================================================

    async def _validate_token(self, acc: Account) -> bool:
        """Check whether the account token is still valid.

        Returns:
            True if valid, False otherwise.
        """
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
            proxy_kw = self._get_proxy_kwarg()
            req_kw: Dict[str, Any] = {
                "headers": headers,
                "ssl": False,
                "timeout": aiohttp.ClientTimeout(total=10),
            }
            if proxy_kw is not None:
                req_kw["proxy"] = proxy_kw
            async with self._session.get(url, **req_kw) as resp:
                return resp.status == 200
        except Exception:
            return False

    # =====================================================================
    # HTTP login
    # =====================================================================

    async def _login(self, acc: Account) -> None:
        """HTTP login for a single account (no candidate rebuild or settings sync).

        Supports proxy when the platform proxy is enabled.
        Retries up to MAX_RETRIES times with exponential back-off.

        Raises:
            Exception: all retries exhausted.
        """
        pwd_hash = acc.password_hash or hash_password(acc.password)
        headers = build_login_headers()
        payload = {"email": acc.username, "password": pwd_hash}

        # Ensure cookies are set on the session before login
        if self._session and self._cookies:
            from yarl import URL
            self._session.cookie_jar.update_cookies(
                self._cookies,
                response_url=URL(BASE_URL),
            )

        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES):
            if attempt > 0:
                await asyncio.sleep(1.0 * (2 ** (attempt - 1)))
            try:
                url = "{}{}".format(BASE_URL, SIGNIN_PATH)
                post_kw: Dict[str, Any] = {
                    "headers": headers,
                    "json": payload,
                    "ssl": False,
                    "timeout": aiohttp.ClientTimeout(total=LOGIN_TIMEOUT),
                }
                proxy_kw = self._get_proxy_kwarg()
                if proxy_kw is not None:
                    post_kw["proxy"] = proxy_kw

                async with self._session.post(url, **post_kw) as resp:
                    if resp.status != 200:
                        err = await resp.text()
                        content_type = resp.headers.get("Content-Type", "")
                        if "text/html" in content_type or err.strip().startswith("<!"):
                            last_exc = Exception(
                                "登录接口被 WAF 拦截 (HTTP {})。请检查 IP 是否可用或启用代理。".format(resp.status)
                            )
                        else:
                            last_exc = Exception(
                                "HTTP {}: {}".format(resp.status, err[:200])
                            )
                        continue

                    data = await resp.json()
                    token = data.get("token", "")
                    if not token:
                        last_exc = Exception("响应中缺少 token")
                        continue

                    acc.token = token
                    acc.user_id = data.get("id", "")
                    acc.password_hash = pwd_hash
                    acc.token_expires = float(data.get("expires_at", 0))
                    acc.is_login = True
                    return
            except Exception as e:
                last_exc = e

        if last_exc:
            acc.is_login = False
            raise last_exc

    # =====================================================================
    # Settings sync
    # =====================================================================

    async def _update_settings(self, acc: Account) -> None:
        """Sync user settings (disable memory, etc.)."""
        if not acc.token or acc.memory_disabled:
            return
        headers = build_headers(acc.token, cookies=self._cookies)
        url = "{}{}".format(BASE_URL, SETTINGS_PATH)
        try:
            post_kw: Dict[str, Any] = {
                "headers": headers,
                "json": DEFAULT_FULL_SETTINGS,
                "ssl": False,
                "timeout": aiohttp.ClientTimeout(total=SETTINGS_TIMEOUT),
            }
            proxy_kw = self._get_proxy_kwarg()
            if proxy_kw is not None:
                post_kw["proxy"] = proxy_kw

            async with self._session.post(url, **post_kw) as resp:
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
        except Exception as e:
            logger.warning(
                "Qwen 设置同步异常 [%s***]: %s", acc.username[:6], e
            )

    # =====================================================================
    # Background cookie refresh
    # =====================================================================

    async def _bg_cookie_refresh(self) -> None:
        """Periodically refresh fingerprint and cookies.

        Task timer persistence: on first iteration, restores the last
        refresh timestamp from disk so restarts don't reset the timer.
        """
        timers = self._load_task_timers()
        last_run = timers.get("cookie_refresh", 0)
        remaining = COOKIE_REFRESH_INTERVAL - (time.time() - last_run)

        while not self._closing:
            sleep_time = remaining if remaining > 0 else COOKIE_REFRESH_INTERVAL
            remaining = -1  # only effective on first iteration

            await asyncio.sleep(sleep_time)
            if not self._closing:
                self._fp = generate_fingerprint()
                self._cookies = generate_cookies(self._fp)
                logger.debug("Qwen: Cookie 已刷新")

                timers["cookie_refresh"] = time.time()
                self._save_task_timers(timers)
