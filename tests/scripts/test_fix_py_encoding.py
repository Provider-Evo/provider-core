from __future__ import annotations

from pathlib import Path

from scripts.fix_py_encoding import _decode, _needs_fix, fix_paths


def test_needs_fix_detects_utf16_bom() -> None:
    """UTF-16 LE BOM 应判定为需修复。"""
    data = "hello".encode("utf-16-le")
    assert _needs_fix(data)


def test_decode_utf16_le() -> None:
    """UTF-16 LE 内容应正确解码。"""
    text = "你好"
    data = b"\xff\xfe" + text.encode("utf-16-le")
    assert _decode(data) == text


def test_fix_paths_writes_utf8(tmp_path: Path) -> None:
    """修复后文件应为无 NUL 的 UTF-8。"""
    target = tmp_path / "sample.py"
    target.write_bytes(b"\xff\xfe" + "x = 1\n".encode("utf-16-le"))
    fixed = fix_paths([target], dry_run=False)
    assert fixed == [target]
    raw = target.read_bytes()
    assert raw.count(0) == 0
    assert target.read_text(encoding="utf-8") == "x = 1\n"
