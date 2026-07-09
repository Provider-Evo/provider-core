"""根级插件路由注册测试。"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_register_plugin_routes_adds_coplan(aiohttp_client_session):
    from src.bootstrap.app_factory import create_application
    from src.core.dispatch.registry import Registry

    registry = Registry()
    await registry.init(aiohttp_client_session)
    app = await create_application(registry, aiohttp_client_session)

    paths = set()
    for route in app.router.routes():
        resource = route.resource
        info = getattr(resource, "canonical", None) or str(resource)
        paths.add(str(info))

    assert any("/v1/coplan/status" in p for p in paths)
    assert any("/coplan" == p or p.endswith("/coplan") for p in paths)
    await registry.close()
