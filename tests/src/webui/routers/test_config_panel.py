from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from src.webui.routers.admin.config_panel import (
    config_get,
    config_put,
    config_reload,
    config_schema_get,
    config_raw_get,
    config_raw_put,
)
from src.webui.services.config_panel_schema import CONFIG_PANEL_SCHEMA, KNOWN_TOP_LEVEL_SECTIONS


@pytest.fixture
def config_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> web.Application:
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    main_cfg = cfg_dir / "main_config.toml"
    main_cfg.write_text(
        '[server]\nversion = "0.0.0-test"\nhost = "127.0.0.1"\nport = 1337\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("src.webui.routers.admin.config_panel.config_dir", lambda: cfg_dir)
    app = web.Application()
    app.router.add_get("/v1/config", config_get)
    app.router.add_put("/v1/config", config_put)
    app.router.add_post("/v1/config/reload", config_reload)
    app.router.add_get("/v1/config/raw", config_raw_get)
    app.router.add_post("/v1/config/raw", config_raw_put)
    app.router.add_get("/v1/admin/config/schema", config_schema_get)
    return app


@pytest.mark.asyncio
async def test_config_get_reads_main_config(config_app: web.Application) -> None:
    async with TestClient(TestServer(config_app)) as client:
        resp = await client.get("/v1/config")
        assert resp.status == 200
        data = await resp.json()
        assert data["server"]["host"] == "127.0.0.1"
        assert data["server"]["port"] == 1337


@pytest.mark.asyncio
async def test_config_schema_get(config_app: web.Application) -> None:
    async with TestClient(TestServer(config_app)) as client:
        resp = await client.get("/v1/admin/config/schema")
        assert resp.status == 200
        data = await resp.json()
        assert data["file"] == CONFIG_PANEL_SCHEMA["file"]
        section_ids = [s["id"] for s in data["sections"]]
        assert "http_pool" in section_ids
        assert "terminal" in section_ids
        assert "autoupdate" not in section_ids


@pytest.mark.asyncio
async def test_config_put_writes_and_reloads(
    config_app: web.Application,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_mock = AsyncMock(return_value=True)
    monkeypatch.setattr("src.webui.routers.admin.config_panel.write_config", write_mock)

    payload = {"server": {"host": "0.0.0.0", "port": 8080}}
    async with TestClient(TestServer(config_app)) as client:
        resp = await client.put("/v1/config", json=payload)
        assert resp.status == 200
        body = await resp.json()
        assert body["status"] == "ok"
    write_mock.assert_awaited_once_with(payload)


@pytest.mark.asyncio
async def test_config_reload(config_app: web.Application, monkeypatch: pytest.MonkeyPatch) -> None:
    reload_mock = AsyncMock()
    monkeypatch.setattr("src.webui.routers.admin.config_panel.reload_config", reload_mock)

    async with TestClient(TestServer(config_app)) as client:
        resp = await client.post("/v1/config/reload")
        assert resp.status == 200
        assert (await resp.json())["status"] == "ok"
    reload_mock.assert_awaited_once()


def test_known_sections_match_schema() -> None:
    assert KNOWN_TOP_LEVEL_SECTIONS == frozenset(s["id"] for s in CONFIG_PANEL_SCHEMA["sections"])


@pytest.mark.asyncio
async def test_config_raw_get(config_app: web.Application) -> None:
    async with TestClient(TestServer(config_app)) as client:
        resp = await client.get("/v1/config/raw")
        assert resp.status == 200
        data = await resp.json()
        assert data["success"] is True
        assert '[server]' in data["content"]
        assert 'port = 1337' in data["content"]


@pytest.mark.asyncio
async def test_config_raw_put(
    config_app: web.Application,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reload_mock = AsyncMock()
    monkeypatch.setattr("src.webui.routers.admin.config_panel.reload_config", reload_mock)

    raw = '[server]\nversion = "0.0.0-test"\nhost = "0.0.0.0"\nport = 8080\n'
    async with TestClient(TestServer(config_app)) as client:
        resp = await client.post("/v1/config/raw", json={"raw_content": raw})
        assert resp.status == 200
        assert (await resp.json())["status"] == "ok"
        get_resp = await client.get("/v1/config/raw")
        assert 'port = 8080' in (await get_resp.json())["content"]
    reload_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_config_raw_put_invalid_toml(config_app: web.Application) -> None:
    async with TestClient(TestServer(config_app)) as client:
        resp = await client.post("/v1/config/raw", json={"raw_content": "not valid toml [[["})
        assert resp.status == 400
        body = await resp.json()
        assert "TOML format error" in body["error"]
