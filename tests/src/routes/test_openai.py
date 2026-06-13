"""Tests for src/routes/openai.py - utility functions and core logic."""
import pytest

from src.routes.openai import (
    _id,
    _cid,
    _bid,
    _fid,
    _aid,
    _tid,
    _rid,
    _vid,
    _uid,
)


class TestIdGenerators:
    def test_id_prefix_format(self):
        result = _id("test")
        assert result.startswith("test-")
        # Should have 24 hex chars after prefix
        parts = result.split("-", 1)
        assert len(parts[1]) == 24

    def test_id_uniqueness(self):
        ids = {_id("test") for _ in range(100)}
        assert len(ids) == 100

    def test_cid_format(self):
        result = _cid()
        assert result.startswith("chatcmpl-")

    def test_bid_format(self):
        result = _bid()
        assert result.startswith("batch-")

    def test_fid_format(self):
        result = _fid()
        assert result.startswith("file-")

    def test_aid_format(self):
        result = _aid()
        assert result.startswith("asst-")

    def test_tid_format(self):
        result = _tid()
        assert result.startswith("thread-")

    def test_rid_format(self):
        result = _rid()
        assert result.startswith("run-")

    def test_vid_format(self):
        result = _vid()
        assert result.startswith("vs-")

    def test_uid_format(self):
        result = _uid()
        assert result.startswith("upload-")

    def test_all_generators_produce_unique_ids(self):
        # Each generator should produce unique IDs
        cids = {_cid() for _ in range(10)}
        bids = {_bid() for _ in range(10)}
        fids = {_fid() for _ in range(10)}

        assert len(cids) == 10
        assert len(bids) == 10
        assert len(fids) == 10

    def test_ids_contain_only_valid_chars(self):
        # Should only contain alphanumeric and hyphens
        import re
        pattern = r"^[a-z]+-[a-f0-9]{24}$"

        for _ in range(20):
            result = _id("test")
            assert re.match(pattern, result), f"Invalid ID format: {result}"
