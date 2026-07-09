from __future__ import annotations

import base64
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from src.webui.routers.session.chat_media import chat_media_get, chat_media_put


@pytest.fixture
def media_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> web.Application:
    monkeypatch.setattr(
        "src.webui.routers.session.chat_media.persist_dir",
        lambda *parts: tmp_path.joinpath(*parts),
    )
    app = web.Application()
    app.router.add_post("/v1/webui/chat-media", chat_media_put)
    app.router.add_get("/v1/webui/chat-media/{id}", chat_media_get)
    return app


@pytest.mark.asyncio
async def test_chat_media_roundtrip(media_app: web.Application) -> None:
    media_id = "a" * 32
    payload = b"hello-image"
    body = {
        "id": media_id,
        "name": "probe.png",
        "mime": "image/png",
        "data_b64": base64.b64encode(payload).decode("ascii"),
    }

    async with TestClient(TestServer(media_app)) as client:
        put_resp = await client.post("/v1/webui/chat-media", json=body)
        assert put_resp.status == 200
        assert (await put_resp.json())["id"] == media_id

        get_resp = await client.get(f"/v1/webui/chat-media/{media_id}")
        assert get_resp.status == 200
        assert get_resp.headers["Content-Type"] == "image/png"
        assert await get_resp.read() == payload


@pytest.mark.asyncio
async def test_chat_media_rejects_invalid_id(media_app: web.Application) -> None:
    async with TestClient(TestServer(media_app)) as client:
        resp = await client.get("/v1/webui/chat-media/not-valid")
        assert resp.status == 400


@pytest.mark.asyncio
async def test_chat_media_not_found(media_app: web.Application) -> None:
    media_id = "b" * 32
    async with TestClient(TestServer(media_app)) as client:
        resp = await client.get(f"/v1/webui/chat-media/{media_id}")
        assert resp.status == 404
