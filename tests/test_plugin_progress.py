"""插件进度 API 测试。"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_update_progress_and_get() -> None:
    from src.webui.routers.admin.plugins.plugin_progress import (
        get_current_progress,
        plugins_progress,
        reset_progress,
        update_progress,
    )

    reset_progress()
    await update_progress("clone", 42, "cloning", operation="install", plugin_id="test.plugin")
    snap = get_current_progress()
    assert snap["progress"] == 42
    assert snap["operation"] == "install"

    from aiohttp import web
    from aiohttp.test_utils import TestClient, TestServer

    app = web.Application()
    app.router.add_get("/progress", plugins_progress)
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/progress")
        data = await resp.json()
        assert data["stage"] == "clone"
    reset_progress()
