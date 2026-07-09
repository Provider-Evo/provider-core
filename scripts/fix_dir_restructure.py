#!/usr/bin/env python3
"""目录全量重构后的 import 与静态路径修正。"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PY_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("from src.core.server.http.auth", "from src.core.server.http.auth"),
    ("from src.core.server.lifecycle.app.app_host", "from src.core.server.lifecycle.app.app_host"),
    ("from src.core.server.lifecycle.app.app import", "from src.core.server.lifecycle.app.app import"),
    ("from src.webui.data.services.config_panel_schema", "from src.webui.data.services.config_panel_schema"),
    ("from src.webui.data.services", "from src.webui.data.services"),
    ("from src.webui.internal.core", "from src.webui.internal.core"),
    ("src.webui.internal.core.", "src.webui.internal.core."),
    ("from src.webui.routers.admin.panels.config_panel", "from src.webui.routers.admin.panels.config_panel"),
    ("from src.webui.routers.admin.panels.webui_config_panel", "from src.webui.routers.admin.panels.webui_config_panel"),
    ("from src.webui.routers.admin.core.admin_auth", "from src.webui.routers.admin.core.admin_auth"),
    ("from src.webui.routers.admin.core.admin import", "from src.webui.routers.admin.core.admin import"),
    ("from src.webui.routers.admin.core.autoupdate", "from src.webui.routers.admin.core.autoupdate"),
    ("from src.webui.routers.admin.core.system", "from src.webui.routers.admin.core.system"),
    ("from src.webui.routers.admin.plugins.plugin_progress", "from src.webui.routers.admin.plugins.plugin_progress"),
    ("from src.webui.routers.admin.plugins.plugin_support", "from src.webui.routers.admin.plugins.plugin_support"),
    ("from src.webui.routers.admin.plugins.plugin_catalog", "from src.webui.routers.admin.plugins.plugin_catalog"),
    ("from src.webui.routers.admin.plugins.plugins import", "from src.webui.routers.admin.plugins.plugins import"),
    ("from src.webui.routers.admin.plugins.runtime.", "from src.webui.routers.admin.plugins.runtime."),
    ("src.webui.routers.admin.panels.config_panel.", "src.webui.routers.admin.panels.config_panel."),
    ("src.webui.routers.admin.panels.webui_config_panel.", "src.webui.routers.admin.panels.webui_config_panel."),
    ("src.webui.routers.admin.plugins.plugin_progress.", "src.webui.routers.admin.plugins.plugin_progress."),
)

STATIC_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ('"/static/files/', '"/static/features/files/'),
    ("'/static/files/", "'/static/features/files/"),
    ('"/static/stats/', '"/static/features/stats/'),
    ("'/static/stats/", "'/static/features/stats/"),
    ('"/static/plugins/', '"/static/features/plugins/'),
    ("'/static/plugins/", "'/static/features/plugins/"),
)


def patch_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text
    if path.suffix == ".py":
        for old, new in PY_REPLACEMENTS:
            text = text.replace(old, new)
    if path.suffix in {".js", ".html", ".css", ".md"}:
        for old, new in STATIC_REPLACEMENTS:
            text = text.replace(old, new)
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> None:
    changed = 0
    patterns = (
        "src/**/*.py",
        "tests/**/*.py",
        "main.py",
        "plugins/**/*.py",
        "scripts/**/*.py",
        "src/webui/static/**/*.js",
        "src/webui/static/**/*.html",
        "src/webui/static/**/*.css",
        "docs-src/**/*.md",
        "README.md",
    )
    for pattern in patterns:
        for path in ROOT.glob(pattern):
            if patch_file(path):
                changed += 1
    print(f"patched {changed} files")


if __name__ == "__main__":
    main()
