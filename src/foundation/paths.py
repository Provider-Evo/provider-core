
from __future__ import annotations

import sys
from pathlib import Path

__all__ = [
    "project_root",
    "resolve_project_root",
    "config_dir",
    "persist_dir",
    "persist_db_dir",
    "persist_json_dir",
]


def resolve_project_root() -> Path:
    """解析项目根目录，兼容 PyInstaller 冻结环境。"""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass).resolve().parent
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


# Project root: src/foundation/paths.py -> repo root (dev) or frozen bundle parent
project_root: Path = resolve_project_root()


def config_dir() -> Path:
    """Return the config/ directory under project root."""
    return project_root / "config"


def persist_dir(*parts: str) -> Path:
    """Return persist/<parts> under project root."""
    return project_root / "persist" / Path(*parts)


def persist_db_dir() -> Path:
    """Return persist/webui/db/ under project root."""
    return persist_dir("webui", "db")


def persist_json_dir() -> Path:
    """Return persist/webui/json/ under project root."""
    return persist_dir("webui", "json")
