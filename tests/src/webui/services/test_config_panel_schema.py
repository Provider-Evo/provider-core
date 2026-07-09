"""Schema 与 template_config.toml 节对齐性测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from src.webui.services.config_panel_schema import (
    CONFIG_PANEL_SCHEMA,
    KNOWN_TOP_LEVEL_SECTIONS,
    WEBUI_CONFIG_KNOWN_KEYS,
    WEBUI_CONFIG_PANEL_SCHEMA,
)

_TEMPLATE_PATH = Path(__file__).resolve().parents[4] / "template" / "template_config.toml"

# 独立标签页管理，不要求出现在主配置 schema
_MAIN_SCHEMA_EXCLUDED = frozenset({"autoupdate"})


def _template_top_level_sections() -> frozenset[str]:
    with open(_TEMPLATE_PATH, "rb") as fh:
        data = tomllib.load(fh)
    return frozenset(k for k, v in data.items() if isinstance(v, dict))


def test_main_schema_covers_template_sections() -> None:
    template_sections = _template_top_level_sections() - _MAIN_SCHEMA_EXCLUDED
    missing = template_sections - KNOWN_TOP_LEVEL_SECTIONS
    assert not missing, f"schema 缺少 template 节: {sorted(missing)}"


def test_webui_schema_has_core_portable_keys() -> None:
    required = {
        "theme",
        "refreshInterval",
        "timeoutMs",
        "layout",
        "sttModel",
        "ttsModel",
        "recordingDeviceId",
        "ttsPrompt",
    }
    assert required <= WEBUI_CONFIG_KNOWN_KEYS


def test_webui_schema_is_flat() -> None:
    assert WEBUI_CONFIG_PANEL_SCHEMA.get("flat") is True
