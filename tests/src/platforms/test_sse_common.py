"""Tests for src.platforms.sse_common module."""

from __future__ import annotations

import pytest

from src.platforms.sse_common import parse_openai_sse_line


class TestParseOpenAiSseLine:
    """Tests for parse_openai_sse_line function."""

    def test_returns_none_for_empty_string(self) -> None:
        assert parse_openai_sse_line("") is None

    def test_returns_none_for_done_marker(self) -> None:
        assert parse_openai_sse_line("[DONE]") is None

    def test_returns_none_for_invalid_json(self) -> None:
        assert parse_openai_sse_line("not json") is None

    def test_returns_none_for_empty_choices(self) -> None:
        assert parse_openai_sse_line('{"choices":[]}') is None

    def test_returns_text_content(self) -> None:
        data = '{"choices":[{"delta":{"content":"hello"}}]}'
        assert parse_openai_sse_line(data) == "hello"

    def test_returns_thinking_content(self) -> None:
        data = '{"choices":[{"delta":{"reasoning_content":"thinking..."}}]}'
        assert parse_openai_sse_line(data) == {"thinking": "thinking..."}

    def test_returns_usage_when_no_choices(self) -> None:
        data = '{"usage":{"prompt_tokens":10,"completion_tokens":20}}'
        result = parse_openai_sse_line(data)
        assert result == {"usage": {"prompt_tokens": 10, "completion_tokens": 20}}

    def test_returns_usage_with_choices(self) -> None:
        data = '{"choices":[{"delta":{}}],"usage":{"prompt_tokens":10}}'
        result = parse_openai_sse_line(data)
        assert result == {"usage": {"prompt_tokens": 10}}

    def test_raises_valueerror_on_error_field(self) -> None:
        data = '{"error":{"message":"rate limited"}}'
        with pytest.raises(ValueError, match="SSE error"):
            parse_openai_sse_line(data)

    def test_returns_none_when_no_content_or_usage(self) -> None:
        data = '{"choices":[{"delta":{}}]}'
        assert parse_openai_sse_line(data) is None