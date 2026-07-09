#!/usr/bin/env python3
"""一次性修正目录重组后的 import 与静态资源路径。"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PY_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("from src.core.dispatch.selector", "from src.core.dispatch.engine.selector"),
    ("from src.core.dispatch.registry", "from src.core.dispatch.engine.registry"),
    ("from src.core.dispatch.gateway", "from src.core.dispatch.engine.gateway"),
    ("from src.core.dispatch.executors", "from src.core.dispatch.engine.executors"),
    ("from src.core.dispatch.runtime_view", "from src.core.dispatch.engine.runtime_view"),
    ("from src.core.dispatch.fncall_context", "from src.core.dispatch.engine.fncall_context"),
    ("from src.core.server.app_host", "from src.core.server.lifecycle.app.app_host"),
    ("from src.core.server.app import", "from src.core.server.lifecycle.app.app import"),
    ("from src.core.server.runner", "from src.core.server.lifecycle.runner"),
    ("from src.core.server.worker", "from src.core.server.lifecycle.worker"),
    ("from src.core.plugins", "from src.core.server.plugins"),
    ("from src.core.observability", "from src.core.utils.observability"),
    ("from src.core.auth", "from src.core.server.http.auth"),
    ("from src.core.http_errors", "from src.core.errors.http_errors"),
    ("from src.webui.data.services", "from src.webui.data.services"),
    ("from src.webui.middleware", "from src.webui.internal.middleware"),
    ("from src.webui.routers.session.terminal_ws_handlers", "from src.webui.routers.session.terminal.terminal_ws_handlers"),
    ("from src.webui.routers.session.terminal_session", "from src.webui.routers.session.terminal.terminal_session"),
    ("from src.webui.routers.session.terminal_output_bridge", "from src.webui.routers.session.terminal.terminal_output_bridge"),
    ("from src.webui.routers.session.terminal import", "from src.webui.routers.session.terminal.terminal import"),
    ("from src.logger", "from src.foundation.logger"),
    ("from src.paths", "from src.foundation.paths"),
    ("import src.logger", "import src.foundation.logger"),
    ("import src.paths", "import src.foundation.paths"),
)

STATIC_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ('"/static/core/', '"/static/base/core/'),
    ("'/static/core/", "'/static/base/core/"),
    ('"/static/config/', '"/static/base/config/'),
    ("'/static/config/", "'/static/base/config/"),
    ('"/static/ui/chat.js', '"/static/ui/chat/chat.js'),
    ('"/static/ui/chat-attachments.js', '"/static/ui/chat/chat-attachments.js'),
    ('"/static/ui/chat-media-persist.js', '"/static/ui/chat/chat-media-persist.js'),
)


def patch_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text
    if path.suffix == ".py":
        for old, new in PY_REPLACEMENTS:
            text = text.replace(old, new)
    if path.suffix in {".js", ".html", ".css"}:
        for old, new in STATIC_REPLACEMENTS:
            text = text.replace(old, new)
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> None:
    changed = 0
    for pattern in ("src/**/*.py", "tests/**/*.py", "main.py", "plugins/**/*.py"):
        for path in ROOT.glob(pattern):
            if patch_file(path):
                changed += 1
    for pattern in ("src/webui/static/**/*.js", "src/webui/static/**/*.html"):
        for path in ROOT.glob(pattern):
            if patch_file(path):
                changed += 1
    print(f"patched {changed} files")


if __name__ == "__main__":
    main()
