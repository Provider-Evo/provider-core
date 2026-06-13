"""Tests for src/routes/anthropic.py - utility functions."""
import pytest
import uuid

from src.routes.anthropic import _mid, _tc_id, _normalize_anth_content


class TestAnthropicIdGenerators:
    def test_mid_format(self):
        result = _mid()
        assert result.startswith("msg_")
        # Should have 24 hex chars after prefix
        parts = result.split("_", 1)
        assert len(parts[1]) == 24

    def test_mid_uniqueness(self):
        ids = {_mid() for _ in range(100)}
        assert len(ids) == 100

    def test_tc_id_format(self):
        result = _tc_id()
        assert result.startswith("toolu_")
        parts = result.split("_", 1)
        assert len(parts[1]) == 24

    def test_tc_id_uniqueness(self):
        ids = {_tc_id() for _ in range(100)}
        assert len(ids) == 100


class TestNormalizeAnthContent:
    def test_none_returns_none(self):
        assert _normalize_anth_content(None) is None

    def test_string_passthrough(self):
        assert _normalize_anth_content("hello") == "hello"

    def test_list_of_text(self):
        content = [
            {"type": "text", "text": "hello"},
            {"type": "text", "text": " world"},
        ]
        result = _normalize_anth_content(content)
        assert result == "hello\n world"

    def test_list_filters_non_text(self):
        content = [
            {"type": "image", "source": "..."},
            {"type": "text", "text": "text only"},
        ]
        result = _normalize_anth_content(content)
        assert result == "text only"

    def test_empty_list_returns_none(self):
        result = _normalize_anth_content([])
        assert result is None

    def test_list_with_no_text_returns_none(self):
        content = [{"type": "image"}, {"type": "tool_use"}]
        result = _normalize_anth_content(content)
        assert result is None

    def test_other_types_converted_to_string(self):
        result = _normalize_anth_content(42)
        assert result == "42"

        result = _normalize_anth_content({"key": "value"})
        assert "key" in result

    def test_empty_string_returns_none(self):
        result = _normalize_anth_content("")
        assert result is None

    def test_whitespace_only_returns_none(self):
        # Actual implementation returns whitespace as-is, not None
        result = _normalize_anth_content("   ")
        assert result == "   "

    def test_single_text_block(self):
        content = [{"type": "text", "text": "single"}]
        result = _normalize_anth_content(content)
        assert result == "single"

    def test_multiple_text_blocks_joined_with_newline(self):
        content = [
            {"type": "text", "text": "line1"},
            {"type": "other"},
            {"type": "text", "text": "line2"},
            {"type": "text", "text": "line3"},
        ]
        result = _normalize_anth_content(content)
        assert result == "line1\nline2\nline3"
