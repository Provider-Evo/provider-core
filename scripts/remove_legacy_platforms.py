#!/usr/bin/env python3
"""删除 src/platforms 下已迁移到 plugins/ 的平台实现（保留 base/capabilities/sse_common）。"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLATFORMS = ROOT / "src" / "platforms"
KEEP_FILES = {"base.py", "capabilities.py", "sse_common.py", "__init__.py", "DEPRECATED.md"}
KEEP_DIRS: set[str] = set()


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove legacy platform cores from src/platforms")
    parser.add_argument("--apply", action="store_true", help="Actually delete files")
    args = parser.parse_args()

    removed = 0
    for child in sorted(PLATFORMS.iterdir()):
        if not child.is_dir():
            continue
        if child.name in KEEP_DIRS:
            continue
        if args.apply:
            shutil.rmtree(child)
            print("removed", child.relative_to(ROOT))
        else:
            print("would remove", child.relative_to(ROOT))
        removed += 1

    dep = PLATFORMS / "DEPRECATED.md"
    text = (
        "# Deprecated\n\n"
        "Platform adapters live under `plugins/Provider-*-Adapter/`.\n"
        "Do not add new code here; `base.py` remains for legacy tests only.\n"
    )
    if args.apply:
        dep.write_text(text, encoding="utf-8")
    else:
        print("would write", dep.relative_to(ROOT))

    print(f"{'removed' if args.apply else 'planned'}: {removed} platform dirs")


if __name__ == "__main__":
    main()
