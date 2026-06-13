from __future__ import annotations

from src.webui.core.local_store import LocalStoreManager


def test_local_store_roundtrip(tmp_path) -> None:
    path = tmp_path / 'local_store.json'
    manager = LocalStoreManager(str(path))
    manager['theme'] = 'dark'
    assert manager['theme'] == 'dark'
    assert 'theme' in manager
    del manager['theme']
    assert manager['theme'] is None
