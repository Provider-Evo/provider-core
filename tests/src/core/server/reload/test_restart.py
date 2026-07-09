"""进程重启模式测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.server.infra.reload.restart import (
    _resolve_fast_restart,
    request_process_restart,
)


def test_resolve_fast_restart_explicit() -> None:
    assert _resolve_fast_restart(True) is True
    assert _resolve_fast_restart(False) is False


def test_resolve_fast_restart_from_config() -> None:
    cfg = MagicMock()
    cfg.server.fast_restart = False
    with patch("src.core.config.get_config", return_value=cfg):
        assert _resolve_fast_restart(None) is False


@pytest.mark.asyncio
async def test_request_process_restart_fast_path() -> None:
    with patch(
        "src.core.server.infra.reload.restart._resolve_fast_restart",
        return_value=True,
    ), patch(
        "src.core.server.infra.reload.restart.request_fast_restart",
        new_callable=AsyncMock,
    ) as fast_mock:
        await request_process_restart(reason="test")
        fast_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_request_process_restart_graceful_path() -> None:
    with patch(
        "src.core.server.infra.reload.restart._resolve_fast_restart",
        return_value=False,
    ), patch(
        "src.core.server.infra.reload.internal.pre_restart.prepare_graceful_restart",
        new_callable=AsyncMock,
    ) as prep_mock, patch(
        "src.core.server.infra.reload.restart.request_graceful_restart",
        new_callable=AsyncMock,
    ) as graceful_mock:
        await request_process_restart(reason="test")
        prep_mock.assert_awaited_once()
        graceful_mock.assert_awaited_once()
