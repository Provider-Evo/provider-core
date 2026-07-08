"""Centralized path helpers for provider-v2."""

from __future__ import annotations

from pathlib import Path

__all__ = ["project_root", "config_dir", "persist_dir", "persist_db_dir", "persist_json_dir"]

# Project root: src/paths.py -> project root
project_root: Path = Path(__file__).resolve().parent.parent


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
