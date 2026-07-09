"""Coplan 策略组存储测试。"""
from __future__ import annotations

from pathlib import Path

from provider_coplan_util.brand import KEY_PREFIX
from provider_coplan_util.store import StrategyStore


def test_create_group_and_key(tmp_path: Path):
    store = StrategyStore(tmp_path)
    group = store.create_group("default", "test")
    assert group["name"] == "default"
    key = store.add_key(group["id"], ["qwen-plus"])
    assert key["key"].startswith(KEY_PREFIX)
    groups = store.list_groups()
    assert len(groups) == 1
    assert len(groups[0]["keys"]) == 1
