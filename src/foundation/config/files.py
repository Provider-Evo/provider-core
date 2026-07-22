"""Canonical config file paths under config/ — create from template when missing."""
from __future__ import annotations

import shutil
from pathlib import Path

from src.foundation.paths import config_dir, project_root

__all__ = [
    "main_config_path",
    "webui_config_path",
    "ensure_main_config_file",
    "ensure_webui_config_file",
]

_MAIN_TEMPLATE = "template_config.toml"
_WEBUI_TEMPLATE = "template_webui_config.toml"


def main_config_path() -> Path:
    """Return ``config/main_config.toml`` (may not exist yet)."""
    return config_dir() / "main_config.toml"


def webui_config_path() -> Path:
    """Return ``config/webui_config.toml`` (may not exist yet)."""
    return config_dir() / "webui_config.toml"


def _template_path(name: str) -> Path:
    return project_root / "template" / name


def _ensure_from_template(target: Path, template_name: str) -> Path:
    config_dir().mkdir(parents=True, exist_ok=True)
    if target.is_file():
        return target
    template = _template_path(template_name)
    if not template.is_file():
        raise FileNotFoundError(
            "模板缺失: template/{}（无法创建 {}）".format(
                template_name, target.relative_to(project_root).as_posix()
            )
        )
    shutil.copy2(template, target)
    return target


def ensure_main_config_file() -> Path:
    """Ensure ``config/main_config.toml`` exists; copy from template if needed."""
    return _ensure_from_template(main_config_path(), _MAIN_TEMPLATE)


def ensure_webui_config_file() -> Path:
    """Ensure ``config/webui_config.toml`` exists; copy from template if needed."""
    return _ensure_from_template(webui_config_path(), _WEBUI_TEMPLATE)
