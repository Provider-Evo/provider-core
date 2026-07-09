from __future__ import annotations

from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from src.webui.routers.admin.webui_config_panel import (
    webui_config_get,
    webui_config_put,
    webui_config_reload,
    webui_config_schema_get,
    webui_config_raw_get,
    webui_config_raw_put,
)
from src.webui.services.config_panel_schema import WEBUI_CONFIG_KNOWN_KEYS, WEBUI_CONFIG_PANEL_SCHEMA


@pytest.fixture
def webui_config_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> web.Application:
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    webui_cfg = cfg_dir / "webui_config.toml"
    webui_cfg.write_text('theme = "dark"\nrefreshInterval = 30\n', encoding="utf-8")
    monkeypatch.setattr("src.webui.routers.admin.webui_config_panel.config_dir", lambda: cfg_dir)
    app = web.Application()
    app.router.add_get("/v1/webui/config", webui_config_get)
    app.router.add_put("/v1/webui/config", webui_config_put)
    app.router.add_post("/v1/webui/config/reload", webui_config_reload)
    app.router.add_get("/v1/webui/config/raw", webui_config_raw_get)
    app.router.add_post("/v1/webui/config/raw", webui_config_raw_put)
    app.router.add_get("/v1/admin/webui/config/schema", webui_config_schema_get)
    return app


@pytest.mark.asyncio
async def test_webui_config_get(webui_config_app: web.Application) -> None:
    async with TestClient(TestServer(webui_config_app)) as client:
        resp = await client.get("/v1/webui/config")
        assert resp.status == 200
        data = await resp.json()
        assert data["theme"] == "dark"
        assert data["refreshInterval"] == 30


@pytest.mark.asyncio
async def test_webui_config_put(webui_config_app: web.Application, tmp_path: Path) -> None:
    payload = {"theme": "light", "layout": "vertical", "sidebarCompressed": True}
    async with TestClient(TestServer(webui_config_app)) as client:
        resp = await client.put("/v1/webui/config", json=payload)
        assert resp.status == 200
        get_resp = await client.get("/v1/webui/config")
        data = await get_resp.json()
        assert data["theme"] == "light"
        assert data["layout"] == "vertical"
        assert data["sidebarCompressed"] is True


@pytest.mark.asyncio
async def test_webui_config_schema(webui_config_app: web.Application) -> None:
    async with TestClient(TestServer(webui_config_app)) as client:
        resp = await client.get("/v1/admin/webui/config/schema")
        assert resp.status == 200
        data = await resp.json()
        assert data["flat"] is True
        assert data["file"] == WEBUI_CONFIG_PANEL_SCHEMA["file"]
        assert "theme" in WEBUI_CONFIG_KNOWN_KEYS


@pytest.mark.asyncio
async def test_webui_config_reload(webui_config_app: web.Application) -> None:
    async with TestClient(TestServer(webui_config_app)) as client:
        resp = await client.post("/v1/webui/config/reload")
        assert resp.status == 200
        body = await resp.json()
        assert body["status"] == "ok"
        assert body["data"]["theme"] == "dark"


@pytest.mark.asyncio
async def test_webui_config_raw_get(webui_config_app: web.Application) -> None:
    async with TestClient(TestServer(webui_config_app)) as client:
        resp = await client.get("/v1/webui/config/raw")
        assert resp.status == 200
        data = await resp.json()
        assert data["success"] is True
        assert 'theme = "dark"' in data["content"]


@pytest.mark.asyncio
async def test_webui_config_raw_put(webui_config_app: web.Application) -> None:
    raw = 'theme = "light"\nrefreshInterval = 60\n'
    async with TestClient(TestServer(webui_config_app)) as client:
        resp = await client.post("/v1/webui/config/raw", json={"raw_content": raw})
        assert resp.status == 200
        get_resp = await client.get("/v1/webui/config")
        data = await get_resp.json()
        assert data["theme"] == "light"
        assert data["refreshInterval"] == 60
