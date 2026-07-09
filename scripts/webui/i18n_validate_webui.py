#!/usr/bin/env python3
"""校验 WebUI locale 文件 key 对齐。"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, Sequence, Set

ROOT = Path(__file__).resolve().parents[2]
LOCALE_DIR = ROOT / "src" / "webui" / "static" / "i18n" / "locales"
SOURCE = "zh"
TARGETS = ("en", "ja", "ko")
PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


def _flatten(data: Dict[str, Any], prefix: str = "") -> Dict[str, str]:
    out: Dict[str, str] = {}
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            out.update(_flatten(value, path))
        elif isinstance(value, str):
            out[path] = value
    return out


def _load_locale(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _placeholders(value: str) -> Set[str]:
    return set(PLACEHOLDER_RE.findall(value))


def main(argv: Sequence[str] | None = None) -> int:
    """公开方法 main。"""
    parser = argparse.ArgumentParser(description="Validate WebUI i18n locale keys")
    parser.parse_args(argv)

    source_path = LOCALE_DIR / f"{SOURCE}.json"
    source_flat = _flatten(_load_locale(source_path))
    errors: list[str] = []

    for lang in TARGETS:
        target_flat = _flatten(_load_locale(LOCALE_DIR / f"{lang}.json"))
        missing = sorted(set(source_flat) - set(target_flat))
        extra = sorted(set(target_flat) - set(source_flat))
        if missing:
            errors.append(f"{lang}: missing keys: {', '.join(missing[:8])}" + (" ..." if len(missing) > 8 else ""))
        if extra:
            errors.append(f"{lang}: extra keys: {', '.join(extra[:8])}" + (" ..." if len(extra) > 8 else ""))
        for key, src_val in source_flat.items():
            tgt_val = target_flat.get(key)
            if tgt_val is None:
                continue
            src_ph = _placeholders(src_val)
            tgt_ph = _placeholders(tgt_val)
            if src_ph != tgt_ph:
                errors.append(f"{lang}: placeholder mismatch at {key}: {src_ph} vs {tgt_ph}")

    if errors:
        for err in errors:
            print(f"ERROR: {err}")
        return 1

    print(f"OK: {len(source_flat)} keys aligned across {SOURCE} + {', '.join(TARGETS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
