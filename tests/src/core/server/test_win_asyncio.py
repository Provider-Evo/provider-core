from __future__ import annotations

import sys

from src.core.server.infra import win_asyncio


def test_apply_windows_asyncio_patches_idempotent() -> None:
    """补丁应可重复调用且不抛异常。"""
    win_asyncio.apply_windows_asyncio_patches()
    win_asyncio.apply_windows_asyncio_patches()


def test_proactor_connection_lost_patch_installed_on_windows() -> None:
    """Windows 上应标记 _call_connection_lost 已打补丁。"""
    if sys.platform != "win32":
        return

    import asyncio.proactor_events as proactor_events

    win_asyncio.apply_windows_asyncio_patches()
    patched = proactor_events._ProactorBasePipeTransport._call_connection_lost
    assert getattr(patched, "_provider_patched", False)
