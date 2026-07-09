"""Log aggregation mixin for QwenClient.

Provides buffered log output for relogin, retry, and login failure events
to prevent log flooding during batch operations.
"""

from __future__ import annotations

import asyncio
from typing import List, Optional, Tuple

from src.logger import get_logger

logger = get_logger(__name__)

_RELOGIN_LOG_BUFFER_SECS = 60
_RETRY_LOG_BUFFER_SECS = 30
_LOGIN_FAIL_LOG_BUFFER_SECS = 60


class LogsMixin:
    """Mixin providing buffered log aggregation methods.

    Expects the composed class to initialize the following attributes
    in ``__init__``:

    - ``_relogin_log_buffer: List[str]``
    - ``_relogin_flush_task: Optional[asyncio.Task]``
    - ``_retry_log_buffer: List[str]``
    - ``_retry_log_flush_task: Optional[asyncio.Task]``
    - ``_login_fail_buffer: List[Tuple[str, str]]``
    - ``_login_fail_flush_task: Optional[asyncio.Task]``
    """

    # =====================================================================
    # Queued relogin log aggregation
    # =====================================================================

    def _log_queued_relogin(self, username_prefix: str) -> None:
        """Buffer a queued-relogin log message; flush after 60 s."""
        self._relogin_log_buffer.append(username_prefix)

        if self._relogin_flush_task is None or self._relogin_flush_task.done():
            self._relogin_flush_task = asyncio.create_task(
                self._flush_relogin_buffer()
            )

    async def _flush_relogin_buffer(self) -> None:
        """Wait for the buffer window, then flush aggregated relogin logs."""
        await asyncio.sleep(_RELOGIN_LOG_BUFFER_SECS)
        self._flush_relogin_buffer_now()

    def _flush_relogin_buffer_now(self) -> None:
        """Immediately flush buffered relogin logs (synchronous)."""
        buffer = self._relogin_log_buffer
        self._relogin_log_buffer = []
        self._relogin_flush_task = None

        if not buffer:
            return

        if len(buffer) == 1:
            logger.debug(
                "Qwen 初始登录: token 无效 [%s***]，排队重登",
                buffer[0],
            )
        else:
            logger.debug(
                "Qwen 初始登录: token 无效 [%s*** and %d other account(s)]，排队重登",
                buffer[0], len(buffer) - 1,
            )

    # =====================================================================
    # Retry log aggregation
    # =====================================================================

    def _log_retry(self, message: str) -> None:
        """Buffer a retry log message; flush after 30 s."""
        self._retry_log_buffer.append(message)

        if self._retry_log_flush_task is None or self._retry_log_flush_task.done():
            self._retry_log_flush_task = asyncio.create_task(
                self._flush_retry_log_buffer()
            )

    async def _flush_retry_log_buffer(self) -> None:
        """Wait for the buffer window, then flush aggregated retry logs."""
        await asyncio.sleep(_RETRY_LOG_BUFFER_SECS)
        self._flush_retry_log_buffer_now()

    def _flush_retry_log_buffer_now(self) -> None:
        """Immediately flush buffered retry logs (synchronous)."""
        buffer = self._retry_log_buffer
        self._retry_log_buffer = []
        self._retry_log_flush_task = None

        if not buffer:
            return

        if len(buffer) == 1:
            logger.debug("Qwen 重试: %s", buffer[0])
        else:
            logger.debug("Qwen 重试: %s (共 %d 条)", buffer[0], len(buffer))

    # =====================================================================
    # Login failure log aggregation
    # =====================================================================

    def _log_login_failure(self, username_prefix: str, error_msg: str) -> None:
        """Buffer a login-failure log message; flush after 60 s."""
        self._login_fail_buffer.append((username_prefix, error_msg))

        if self._login_fail_flush_task is None or self._login_fail_flush_task.done():
            self._login_fail_flush_task = asyncio.create_task(
                self._flush_login_fail_buffer()
            )

    async def _flush_login_fail_buffer(self) -> None:
        """Wait for the buffer window, then flush aggregated login-failure logs."""
        await asyncio.sleep(_LOGIN_FAIL_LOG_BUFFER_SECS)
        self._flush_login_fail_buffer_now()

    def _flush_login_fail_buffer_now(self) -> None:
        """Immediately flush buffered login-failure logs (synchronous)."""
        buffer = self._login_fail_buffer
        self._login_fail_buffer = []
        self._login_fail_flush_task = None

        if not buffer:
            return

        first_prefix, first_error = buffer[0]
        if len(buffer) == 1:
            logger.warning(
                "Qwen 初始登录失败 [%s***]: %s",
                first_prefix, first_error,
            )
        else:
            logger.warning(
                "Qwen 初始登录失败 [%s*** and %d other account(s)]: %s",
                first_prefix, len(buffer) - 1, first_error,
            )
