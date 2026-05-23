from __future__ import annotations

import json
from pathlib import Path

from src.platforms.qwen.accounts import Account
from src.platforms.qwen.core.persistence import load_persist, save_persist
from src.platforms.qwen.core.proxy import ProxyState


def test_qwen_persistence_roundtrip(tmp_path, monkeypatch) -> None:
    persist_path = tmp_path / "qwen_usage.json"
    monkeypatch.setattr("src.platforms.qwen.core.persistence.PERSIST_PATH", str(persist_path))
    accounts = {
        "user@example.com": Account(username="user@example.com", password="pw", token="token-1", user_id="uid-1"),
    }
    cookies = {"ssxmod_itna": "cookie-a"}
    proxy = ProxyState()
    proxy.set_enabled(True, auto=True)
    save_persist(accounts, cookies, proxy)
    data = json.loads(persist_path.read_text(encoding="utf-8"))
    assert data["accounts"]["user@example.com"]["token"] == "token-1"
    restored_accounts = {
        "user@example.com": Account(username="user@example.com", password="pw"),
    }
    restored_proxy = ProxyState()
    restored_cookies = load_persist(restored_accounts, {}, restored_proxy)
    assert restored_accounts["user@example.com"].token == "token-1"
    assert restored_cookies["ssxmod_itna"] == "cookie-a"
