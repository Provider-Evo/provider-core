"""Centralized path helpers for provider-v2."""

from __future__ import annotations

from pathlib import Path

__all__ = ["project_root", "config_dir", "persist_dir", "persist_db_dir", "persist_json_dir"]

# Project root: src/paths.py -> project root
project_root: Path = Path(__file__).resolve().parent.parent


def config_dir() -> Path:
    """中文说明：config_dir。

Return the config/ directory under project root."""
    return project_root / "config"


def persist_dir(*parts: str) -> Path:
    """中文说明：persist_dir。

Return persist/<parts> under project root."""
    return project_root / "persist" / Path(*parts)


def persist_db_dir() -> Path:
    """中文说明：persist_db_dir。

Return persist/webui/db/ under project root."""
    return persist_dir("webui", "db")


def persist_json_dir() -> Path:
    """中文说明：persist_json_dir。

Return persist/webui/json/ under project root."""
    return persist_dir("webui", "json")
