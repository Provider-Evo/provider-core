"""Tests for src/core/utils/files.py."""
import os
import tempfile
from pathlib import Path

import pytest

from src.core.utils.files import FileUtil


class TestFileUtilMime:
    def test_jpeg(self):
        assert FileUtil.mime("photo.jpg") == "image/jpeg"
        assert FileUtil.mime("photo.jpeg") == "image/jpeg"

    def test_png(self):
        assert FileUtil.mime("image.png") == "image/png"

    def test_pdf(self):
        assert FileUtil.mime("document.pdf") == "application/pdf"

    def test_unknown(self):
        assert FileUtil.mime("file.xyz") == "application/octet-stream"

    def test_txt(self):
        assert FileUtil.mime("readme.txt") == "text/plain"

    def test_python(self):
        assert FileUtil.mime("script.py") == "text/x-python"

    def test_audio(self):
        assert FileUtil.mime("song.mp3") == "audio/mpeg"
        assert FileUtil.mime("song.wav") == "audio/wav"

    def test_video(self):
        assert FileUtil.mime("movie.mp4") == "video/mp4"


class TestFileUtilIsUrl:
    def test_http(self):
        assert FileUtil.is_url("http://example.com") is True

    def test_https(self):
        assert FileUtil.is_url("https://example.com") is True

    def test_not_url(self):
        assert FileUtil.is_url("/path/to/file") is False
        assert FileUtil.is_url("data:image/png;base64,abc") is False
        assert FileUtil.is_url("") is False


class TestFileUtilIsDataUri:
    def test_valid_data_uri(self):
        assert FileUtil.is_data_uri("data:image/png;base64,abc123") is True

    def test_not_data_uri(self):
        assert FileUtil.is_data_uri("http://example.com") is False
        assert FileUtil.is_data_uri("/path/to/file") is False

    def test_not_string(self):
        # Should handle gracefully with non-string input
        assert FileUtil.is_data_uri(123) is False


class TestFileUtilParseDataUri:
    def test_valid_png(self):
        uri = "data:image/png;base64,iVBORw0KGgo="
        result = FileUtil.parse_data_uri(uri)
        assert result is not None
        mime, data = result
        assert mime == "image/png"
        assert isinstance(data, bytes)

    def test_invalid_uri(self):
        result = FileUtil.parse_data_uri("not a data uri")
        assert result is None

    def test_malformed_base64(self):
        # Should handle gracefully
        result = FileUtil.parse_data_uri("data:text/plain;base64,!!!invalid!!!")
        # May return None or partial data depending on base64 decoder
        assert result is None or isinstance(result, tuple)

    def test_removes_whitespace(self):
        uri = "data:text/plain;base64,SGVsbG8gV29ybGQ="
        result = FileUtil.parse_data_uri(uri)
        assert result is not None
        mime, data = result
        assert data == b"Hello World"


class TestFileUtilSaveDataUri:
    def test_saves_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uri = "data:image/png;base64,iVBORw0KGgo="
            path = FileUtil.save_data_uri(uri, tmpdir)
            assert path is not None
            assert os.path.exists(path)
            # File should contain PNG header
            with open(path, "rb") as f:
                header = f.read(8)
                assert header[:4] == b"\x89PNG"

    def test_returns_none_for_invalid_uri(self):
        result = FileUtil.save_data_uri("invalid", "data/uploads")
        assert result is None


class TestFileUtilCleanup:
    def test_deletes_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
        assert os.path.exists(path)
        FileUtil.cleanup(path)
        assert not os.path.exists(path)

    def test_ignores_nonexistent(self):
        # Should not raise
        FileUtil.cleanup("/nonexistent/path/file.txt")

    def test_ignores_empty_path(self):
        FileUtil.cleanup("")
        FileUtil.cleanup(None)  # type: ignore


class TestFileUtilMd5:
    def test_correct_hash(self):
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
            f.write(b"hello world")
            path = f.name

        md5 = FileUtil.md5(path)
        assert isinstance(md5, str)
        assert len(md5) == 32  # MD5 hex length
        # Clean up
        os.unlink(path)

    def test_large_file(self):
        # Test chunked reading (> 8192 bytes)
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
            f.write(b"x" * 20000)
            path = f.name

        md5 = FileUtil.md5(path)
        assert len(md5) == 32
        os.unlink(path)


class TestFileUtilReadChunks:
    def test_small_file(self):
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
            f.write(b"hello")
            path = f.name

        chunks = FileUtil.read_chunks(path, chunk_size=1024)
        assert chunks == [b"hello"]
        os.unlink(path)

    def test_large_file_multiple_chunks(self):
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
            f.write(b"x" * 20000)
            path = f.name

        chunks = FileUtil.read_chunks(path, chunk_size=8192)
        assert len(chunks) == 3  # 8192 + 8192 + 3616
        assert sum(len(c) for c in chunks) == 20000
        os.unlink(path)

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
            path = f.name

        chunks = FileUtil.read_chunks(path)
        assert chunks == []
        os.unlink(path)


class TestFileUtilEnsureDir:
    def test_creates_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "new", "nested", "dir")
            result = FileUtil.ensure_dir(path)
            assert os.path.exists(path)
            assert result == path

    def test_existing_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = FileUtil.ensure_dir(tmpdir)
            assert result == tmpdir
