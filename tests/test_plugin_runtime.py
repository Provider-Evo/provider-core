"""根级插件运行时测试。"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_plugin_runtime_loads_enabled_plugins(aiohttp_client_session):
    from src.core.server.plugins.runtime import PluginRuntime

    runtime = PluginRuntime()
    await runtime.init(aiohttp_client_session)
    summary = runtime.get_plugin_summary()
    assert summary["loaded"] >= 1
    assert summary["failed"] == 0
    platforms = [getattr(a, "name", "") for a in runtime.platform_adapters()]
    assert "zen" in platforms
    await runtime.close()


@pytest.mark.asyncio
async def test_plugin_runtime_fault_tolerance(aiohttp_client_session, monkeypatch):
    from src.core.server.plugins.runtime import PluginRuntime

    runtime = PluginRuntime()
    await runtime.init(aiohttp_client_session)
    runtime._failed["test.broken"] = "simulated"
    statuses = runtime.get_plugin_summary()
    assert statuses["failed"] >= 1
    await runtime.close()
