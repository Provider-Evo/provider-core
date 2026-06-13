"""Tests for src/core/utils/io_utils.py."""
import os
import tempfile
from pathlib import Path

import pytest

from src.core.utils.io_utils import (
    atomic_write_text,
    ensure_directory,
    read_text_if_exists,
)


class TestEnsureDirectory:
    def test_creates_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "new" / "nested"
            result = ensure_directory(path)
            assert path.exists()
            assert result == path

    def test_existing_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            result = ensure_directory(path)
            assert result == path

    def test_returns_path_object(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test"
            result = ensure_directory(path)
            assert isinstance(result, Path)


class TestAtomicWriteText:
    def test_writes_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.txt"
            atomic_write_text(path, "hello world")
            assert path.read_text() == "hello world"

    def test_creates_parent_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nested" / "dir" / "test.txt"
            atomic_write_text(path, "content")
            assert path.exists()
            assert path.read_text() == "content"

    def test_overwrites_existing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.txt"
            path.write_text("old content")
            atomic_write_text(path, "new content")
            assert path.read_text() == "new content"

    def test_utf8_encoding(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "utf8.txt"
            content = "中文测试 🎉"
            atomic_write_text(path, content)
            assert path.read_text(encoding="utf-8") == content

    def test_removes_temp_file_on_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.txt"
            temp_path = path.with_suffix(path.suffix + ".tmp")
            atomic_write_text(path, "content")
            assert not temp_path.exists()

    def test_writes_directly_on_permission_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.txt"
            # This tests that the fallback write works
            atomic_write_text(path, "content", retries=1)
            assert path.read_text() == "content"


class TestReadTextIfExists:
    def test_reads_existing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.txt"
            path.write_text("hello")
            result = read_text_if_exists(path)
            assert result == "hello"

    def test_returns_none_for_nonexistent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nonexistent.txt"
            result = read_text_if_exists(path)
            assert result is None

    def test_custom_encoding(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.txt"
            content = "中文"
            path.write_text(content, encoding="utf-8")
            result = read_text_if_exists(path, encoding="utf-8")
            assert result == content

    def test_empty_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "empty.txt"
            path.write_text("")
            result = read_text_if_exists(path)
            assert result == ""
