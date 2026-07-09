"""插件管理 API 单元测试。"""
from __future__ import annotations

import pytest

from src.webui.routers.admin.plugins.plugin_catalog import _parse_host_version
from src.webui.routers.admin.plugins.plugin_support import validate_plugin_id


def test_validate_plugin_id_rejects_traversal() -> None:
    assert validate_plugin_id("nichengfuben.provider-qwen-adapter") is True
    assert validate_plugin_id("../evil") is False
    assert validate_plugin_id("a/b") is False


def test_parse_host_version_numeric() -> None:
    parsed = _parse_host_version("2.2.286")
    assert parsed == {"version_major": 2, "version_minor": 2, "version_patch": 286}


@pytest.mark.asyncio
async def test_plugins_config_bundle_not_found() -> None:
    from aiohttp import web
    from aiohttp.test_utils import TestClient, TestServer

    from src.webui.routers.admin.plugins.plugins import plugins_config_bundle

    app = web.Application()
    app.router.add_get("/bundle/{plugin_id}", plugins_config_bundle)
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/bundle/nonexistent-plugin-id-xyz")
        assert resp.status == 404


def test_defaults_from_schema_boolean_and_nested() -> None:
    from src.webui.routers.admin.plugins.plugins import _defaults_from_schema

    schema = {
        "type": "object",
        "properties": {
            "server": {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean", "default": True},
                    "port": {"type": "integer", "default": 8787},
                },
            },
            "name": {"type": "string"},
        },
    }
    defaults = _defaults_from_schema(schema)
    assert defaults["server"]["enabled"] is True
    assert defaults["server"]["port"] == 8787
    assert defaults["name"] == ""


@pytest.mark.asyncio
async def test_plugins_mirrors_list() -> None:
    from aiohttp import web
    from aiohttp.test_utils import TestClient, TestServer

    from src.webui.routers.admin.plugins.runtime.mirrors import plugins_mirror_list

    app = web.Application()
    app.router.add_get("/mirrors", plugins_mirror_list)
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/mirrors")
        assert resp.status == 200
        data = await resp.json()
        assert data.get("success") is True
        assert isinstance(data.get("mirrors"), list)


@pytest.mark.asyncio
async def test_plugin_runtime_circuit_statuses() -> None:
    from src.core.server.plugins.runtime import PluginRuntime

    runtime = PluginRuntime()
    statuses = runtime.get_plugin_circuit_statuses()
    assert isinstance(statuses, dict)


@pytest.mark.asyncio
async def test_plugins_host_version_handler() -> None:
    from aiohttp import web
    from aiohttp.test_utils import TestClient, TestServer

    from src.webui.routers.admin.plugins.plugin_catalog import plugins_host_version

    app = web.Application()
    app.router.add_get("/version", plugins_host_version)
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/version")
        assert resp.status == 200
        data = await resp.json()
        assert "version" in data
