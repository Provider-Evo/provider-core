"""策略组持久化。"""
from __future__ import annotations

import json
import secrets
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

from provider_coplan_util.brand import KEY_PREFIX

__all__ = ["StrategyStore"]


def _new_key() -> str:
    return KEY_PREFIX + secrets.token_hex(8)


class StrategyStore:
    def __init__(self, data_dir: Path) -> None:
        self._dir = data_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._groups_path = self._dir / "strategy_groups.json"
        if not self._groups_path.is_file():
            self._groups_path.write_text("[]", encoding="utf-8")

    def list_groups(self) -> List[Dict[str, Any]]:
        return json.loads(self._groups_path.read_text(encoding="utf-8"))

    def _save(self, groups: List[Dict[str, Any]]) -> None:
        self._groups_path.write_text(
            json.dumps(groups, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def create_group(self, name: str, description: str = "") -> Dict[str, Any]:
        groups = self.list_groups()
        entry = {
            "id": str(uuid.uuid4()),
            "name": name,
            "description": description,
            "keys": [],
            "created_at": int(time.time()),
        }
        groups.append(entry)
        self._save(groups)
        return entry

    def add_key(self, group_id: str, models: List[str] | None = None) -> Dict[str, Any]:
        groups = self.list_groups()
        for group in groups:
            if group.get("id") != group_id:
                continue
            key_entry = {
                "id": str(uuid.uuid4()),
                "key": _new_key(),
                "models": list(models or []),
                "created_at": int(time.time()),
            }
            group.setdefault("keys", []).append(key_entry)
            self._save(groups)
            return key_entry
        raise KeyError(group_id)
