#!/usr/bin/env python3
"""检测并将误存为 UTF-16 的 Python 文件转回 UTF-8。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterator, List, Sequence

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_ROOTS: tuple[str, ...] = ("src", "scripts", "tests", "main.py")


def _iter_py_files(roots: Sequence[str]) -> Iterator[Path]:
    for root_name in roots:
        base = ROOT / root_name if root_name != "main.py" else ROOT / "main.py"
        if base.is_file():
            yield base
            continue
        if base.is_dir():
            yield from base.rglob("*.py")


def _needs_fix(data: bytes) -> bool:
    if data.count(0) > 0:
        return True
    return data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff")


def _decode(data: bytes) -> str:
    if data.startswith(b"\xff\xfe"):
        return data[2:].decode("utf-16-le")
    if data.startswith(b"\xfe\xff"):
        return data[2:].decode("utf-16-be")
    return data.decode("utf-8", errors="surrogateescape")


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def fix_paths(paths: Sequence[Path], *, dry_run: bool) -> List[Path]:
    """公开方法 fix_paths。"""
    fixed: List[Path] = []
    for path in paths:
        data = path.read_bytes()
        if not _needs_fix(data):
            continue
        if dry_run:
            print(f"would fix: {_display_path(path)}")
        else:
            text = _decode(data)
            path.write_text(text, encoding="utf-8", newline="\n")
            print(f"fixed: {_display_path(path)}")
        fixed.append(path)
    return fixed


def main(argv: Sequence[str] | None = None) -> int:
    """公开方法 main。"""
    parser = argparse.ArgumentParser(description="修复 UTF-16 / NUL 污染的 .py 文件")
    parser.add_argument("paths", nargs="*", help="指定文件；默认扫描 src scripts tests main.py")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.paths:
        targets = [Path(p) if Path(p).is_absolute() else ROOT / p for p in args.paths]
    else:
        targets = list(_iter_py_files(DEFAULT_ROOTS))

    fixed = fix_paths(targets, dry_run=args.dry_run)
    if not fixed:
        print("OK: 无需修复")
        return 0
    return 0 if args.dry_run else 0


if __name__ == "__main__":
    raise SystemExit(main())
