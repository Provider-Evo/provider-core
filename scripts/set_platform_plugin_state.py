#!/usr/bin/env python3
"""启用/禁用平台插件 manifest。"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ROOT / "plugins"

DISABLE = {
    "Provider-Aitianhu2-Adapter",
    "Provider-Apiairforce-Adapter",
    "Provider-Azuretranslate-Adapter",
    "Provider-Caiyuesbk-Adapter",
    "Provider-Cerebras-Adapter",
    "Provider-Chutes-Adapter",
    "Provider-Codebuddy-Adapter",
    "Provider-Cursor-Adapter",
    "Provider-Deepl-Adapter",
    "Provider-Deepseek-Adapter",
    "Provider-Googletranslate-Adapter",
    "Provider-N1n-Adapter",
    "Provider-Noobkeys-Adapter",
    "Provider-Nvidia-Adapter",
    "Provider-Openrouter-Adapter",
    "Provider-OpencodeZen-Adapter",
    "Provider-Perplexity-Adapter",
    "Provider-Yandextranslate-Adapter",
}

ENABLE = {
    "Provider-Zen-Adapter",
}


def _disable(plugin_dir: Path) -> None:
    active = plugin_dir / "_manifest.json"
    disabled = plugin_dir / "_manifest.json.disabled"
    if active.is_file():
        if disabled.is_file():
            disabled.unlink()
        active.rename(disabled)
        print("disabled", plugin_dir.name)


def _enable(plugin_dir: Path) -> None:
    active = plugin_dir / "_manifest.json"
    disabled = plugin_dir / "_manifest.json.disabled"
    if disabled.is_file():
        if active.is_file():
            active.unlink()
        disabled.rename(active)
        print("enabled", plugin_dir.name)
    elif not active.is_file():
        print("missing manifest", plugin_dir.name)


def main() -> None:
    for name in sorted(DISABLE):
        path = PLUGINS / name
        if path.is_dir():
            _disable(path)
    for name in sorted(ENABLE):
        path = PLUGINS / name
        if path.is_dir():
            _enable(path)


if __name__ == "__main__":
    main()
