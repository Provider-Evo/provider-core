#!/usr/bin/env python3
"""将插件 import 从 src.platforms 迁移到 provider_sdk / 本地包。"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ROOT / "plugins"

REPLACEMENTS = [
    ("from src.platforms.base import", "from provider_sdk.extensions.platform.adapter import"),
    ("from src.platforms.sse_common import", "from provider_sdk.extensions.platform.sse_common import"),
]


def _package_name(plugin_dir: Path) -> str:
    for child in plugin_dir.iterdir():
        if child.is_dir() and child.name.startswith("provider_"):
            return child.name
    slug = plugin_dir.name.replace("Provider-", "").replace("-Adapter", "").replace("-Util", "")
    return "provider_" + slug.lower().replace("-", "")


def _platform_slug(plugin_dir: Path) -> str:
    name = plugin_dir.name
    if name.startswith("Provider-"):
        name = name[len("Provider-") :]
    for suffix in ("-Adapter", "-Util"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name.lower().replace("-", "")


def migrate_file(path: Path, platform_slug: str, package: str, apply: bool) -> int:
    text = path.read_text(encoding="utf-8")
    original = text
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    pattern = re.compile(rf"from src\.platforms\.{re.escape(platform_slug)}(\.[a-zA-Z0-9_.]+)? import")
    def repl(match: re.Match[str]) -> str:
        suffix = match.group(1) or ""
        return f"from {package}{suffix} import"
    text = pattern.sub(repl, text)
    if text != original:
        if apply:
            path.write_text(text, encoding="utf-8")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    changed = 0
    for plugin_dir in sorted(PLUGINS.glob("Provider-*")):
        if not plugin_dir.is_dir():
            continue
        package = _package_name(plugin_dir)
        slug = _platform_slug(plugin_dir)
        for py in plugin_dir.rglob("*.py"):
            changed += migrate_file(py, slug, package, args.apply)
    print(f"{'updated' if args.apply else 'would update'} {changed} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
