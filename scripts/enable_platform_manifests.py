#!/usr/bin/env python3
"""启用 plugins/ 下被禁用的平台 manifest（保留已合并的 opencode/zen）。"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ROOT / "plugins"
SKIP = {"Provider-Opencode-Adapter", "Provider-Zen-Adapter"}


def main() -> None:
    enabled = 0
    for plugin_dir in sorted(PLUGINS.glob("Provider-*-Adapter")):
        if plugin_dir.name in SKIP:
            print("skip", plugin_dir.name)
            continue
        disabled = plugin_dir / "_manifest.json.disabled"
        active = plugin_dir / "_manifest.json"
        if disabled.is_file() and not active.is_file():
            disabled.rename(active)
            enabled += 1
            print("enabled", plugin_dir.name)
    print(f"done: {enabled} manifest(s) enabled")


if __name__ == "__main__":
    main()
