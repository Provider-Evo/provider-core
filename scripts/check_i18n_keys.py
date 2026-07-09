#!/usr/bin/env python3
"""Scan WebUI i18n keys vs locale JSON parity."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "webui" / "static"
LOCALES = ROOT / "i18n" / "locales"


def flatten(data: dict, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in data.items():
        full = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            out.update(flatten(value, full))
        else:
            out[str(full)] = str(value)
    return out


def has_key(data: dict, key: str) -> bool:
    node: object = data
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return isinstance(node, str)


def collect_used_keys() -> set[str]:
    keys: set[str] = set()
    pattern = re.compile(r"""(?:t|_t|_tOr)\(['"]([a-z][a-z0-9]*(?:\.[a-zA-Z0-9_]+)+)['"]""")
    for path in ROOT.rglob("*.js"):
        keys.update(pattern.findall(path.read_text(encoding="utf-8", errors="ignore")))
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    keys.update(re.findall(r'data-i18n(?:-placeholder)?="([^"]+)"', html))
    return keys


def main() -> int:
    zh = json.loads((LOCALES / "zh.json").read_text(encoding="utf-8"))
    used = collect_used_keys()
    missing_zh = sorted(
        key for key in used
        if not has_key(zh, key) and not key.startswith("datepicker.month") and not key.startswith("datepicker.weekday")
    )
    if missing_zh:
        print("Missing in zh.json:")
        for key in missing_zh:
            print(f"  {key}")
        return 1

    zh_flat = flatten(zh)
    exit_code = 0
    for lang in ("en", "ja", "ko"):
        loc = json.loads((LOCALES / f"{lang}.json").read_text(encoding="utf-8"))
        loc_flat = flatten(loc)
        missing = sorted(set(zh_flat) - set(loc_flat))
        if missing:
            exit_code = 1
            print(f"Missing in {lang}.json ({len(missing)}):")
            for key in missing[:20]:
                print(f"  {key}")
            if len(missing) > 20:
                print(f"  ... and {len(missing) - 20} more")
    if exit_code == 0:
        print(f"OK: {len(used)} UI keys, {len(zh_flat)} zh keys, en/ja/ko aligned")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
