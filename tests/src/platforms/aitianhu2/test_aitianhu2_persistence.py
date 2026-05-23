from __future__ import annotations

import asyncio

import aiohttp
from yarl import URL

from src.platforms.aitianhu2.core.persistence import extract_cookie_state, load_persist, restore_cookie_jar, save_persist


def test_aitianhu2_persistence_roundtrip(tmp_path, monkeypatch) -> None:
    persist_path = tmp_path / "aitianhu2_state.json"
    monkeypatch.setattr("src.platforms.aitianhu2.core.persistence.PERSIST_PATH", persist_path)

    async def runner() -> None:
        async with aiohttp.ClientSession() as session:
            session.cookie_jar.update_cookies({"gfsessionid": "session-a", "carid": "car-a"}, response_url=URL("https://3h96y9.aitianhu2.top"))
            save_persist(session, device_id="device-a", authenticated=True, models=["gpt-5-5"], api_key_hint="12345678")
        data = load_persist()
        assert data["device_id"] == "device-a"
        assert data["authenticated"] is True
        async with aiohttp.ClientSession() as restored_session:
            restore_cookie_jar(restored_session, data["cookies"])
            cookies = extract_cookie_state(restored_session)
            assert cookies["gfsessionid"] == "session-a"
            assert cookies["carid"] == "car-a"

    asyncio.run(runner())
