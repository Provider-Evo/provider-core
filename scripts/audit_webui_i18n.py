#!/usr/bin/env python3
"""审计 WebUI 静态资源中的 i18n 键是否与 locale 对齐。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterator, List, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "webui" / "static"
LOCALES = STATIC / "i18n" / "locales"
LOCALE_LANGS: Tuple[str, ...] = ("zh", "en", "ja", "ko")


def _flatten(data: Dict[str, object], prefix: str = "") -> Dict[str, str]:
    out: Dict[str, str] = {}
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            out.update(_flatten(value, path))
        elif isinstance(value, str):
            out[path] = value
    return out


def _load_locales() -> Dict[str, Dict[str, str]]:
    locales: Dict[str, Dict[str, str]] = {}
    for lng in LOCALE_LANGS:
        locales[lng] = _flatten(json.loads((LOCALES / f"{lng}.json").read_text(encoding="utf-8")))
    return locales


def _iter_static_files() -> Iterator[Path]:
    for path in sorted(STATIC.rglob("*")):
        if path.suffix in (".html", ".js"):
            yield path


def audit() -> Tuple[List[Tuple[str, str, str]], Dict[str, List[str]], Dict[str, List[str]]]:
    """返回 (畸形 HTML, zh 缺失键, 各语言与 zh 的差异)。"""
    locales = _load_locales()
    zh_keys = set(locales["zh"])
    html_keys: Dict[str, Set[str]] = {}
    placeholder_keys: Dict[str, Set[str]] = {}
    t_keys: Dict[str, Set[str]] = {}
    malformed: List[Tuple[str, str, str]] = []

    for path in _iter_static_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = str(path.relative_to(STATIC))
        for match in re.finditer(r'data-i18n="([^"]+)"', text):
            html_keys.setdefault(match.group(1), set()).add(rel)
        for match in re.finditer(r'data-i18n-placeholder="([^"]+)"', text):
            placeholder_keys.setdefault(match.group(1), set()).add(rel)
        if path.suffix == ".js":
            for match in re.finditer(r"""\bt\(['"]([a-zA-Z0-9_.]+)['"]""", text):
                t_keys.setdefault(match.group(1), set()).add(rel)
        for match in re.finditer(r'>(\s*)data-i18n="([^"]+)"', text):
            malformed.append((match.group(2), rel, "text-leak"))

    all_used: Dict[str, Set[str]] = {}
    for mapping in (html_keys, placeholder_keys, t_keys):
        for key, sources in mapping.items():
            all_used.setdefault(key, set()).update(sources)

    missing_zh = {
        key: sorted(sources)
        for key, sources in sorted(all_used.items())
        if key not in zh_keys
    }
    parity: Dict[str, List[str]] = {}
    for lng in LOCALE_LANGS[1:]:
        diff = sorted(zh_keys - set(locales[lng]))
        if diff:
            parity[lng] = diff
    return malformed, missing_zh, parity


def main(argv: Sequence[str] | None = None) -> int:
    """公开方法 main。"""
    parser = argparse.ArgumentParser(description="审计 WebUI i18n 键")
    parser.parse_args(argv)
    malformed, missing_zh, parity = audit()
    errors = 0
    if malformed:
        errors += len(malformed)
        print("=== MALFORMED HTML ===")
        for item in malformed:
            print(item)
        print()
    if missing_zh:
        errors += len(missing_zh)
        print(f"=== MISSING IN zh.json ({len(missing_zh)} keys) ===")
        for key, sources in missing_zh.items():
            print(key)
            for src in sources[:4]:
                print(" ", src)
        print()
    if parity:
        print("=== LOCALE PARITY ===")
        for lng, keys in parity.items():
            print(f"{lng}: {len(keys)} missing vs zh")
            for key in keys[:10]:
                print(" ", key)
        errors += sum(len(v) for v in parity.values())
    if errors:
        return 1
    print("OK: WebUI i18n keys aligned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
