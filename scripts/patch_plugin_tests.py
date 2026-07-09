#!/usr/bin/env python3
"""批量修复插件 test_manifest_exists 接受 disabled manifest。"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_BODY = '''def test_manifest_exists():
    """验证 manifest 文件存在（enabled 或 disabled）。"""
    from pathlib import Path
    parent = Path(__file__).parent.parent
    manifest = parent / "_manifest.json"
    disabled = parent / "_manifest.json.disabled"
    assert manifest.is_file() or disabled.is_file()
'''


def main() -> None:
    for path in ROOT.glob("plugins/*/tests/test_plugin.py"):
        text = path.read_text(encoding="utf-8")
        if "disabled.is_file()" in text:
            continue
        start = text.find("def test_manifest_exists")
        end = text.find("\n\n", start)
        if start < 0 or end < 0:
            continue
        new_text = text[:start] + TEST_BODY + text[end:]
        path.write_text(new_text, encoding="utf-8")
        print("patched", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
