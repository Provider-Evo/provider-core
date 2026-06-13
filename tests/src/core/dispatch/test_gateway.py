"""Tests for src/core/dispatch/gateway.py."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.dispatch.gateway import dispatch, _fallback_usage, _normalize_usage


class TestFallbackUsage:
    def test_basic_calculation(self):
        result = _fallback_usage(300, "hello world")
        assert result["prompt_tokens"] == 100  # 300 // 3
        assert result["completion_tokens"] == 3  # 11 // 3
        assert result["total_tokens"] == 103

    def test_min_values(self):
        result = _fallback_usage(0, "")
        assert result["prompt_tokens"] == 1  # max(0, 1)
        assert result["completion_tokens"] == 0


class TestNormalizeUsage:
    def test_with_valid_data(self):
        raw = {"prompt_tokens": 100, "completion_tokens": 50}
        result = _normalize_usage(raw, 300, "test")
        assert result["prompt_tokens"] == 100
        assert result["completion_tokens"] == 50
        assert result["total_tokens"] == 150

    def test_with_alternate_keys(self):
        raw = {"input_tokens": 80, "output_tokens": 40}
        result = _normalize_usage(raw, 300, "test")
        assert result["prompt_tokens"] == 80
        assert result["completion_tokens"] == 40

    def test_fallback_when_zero(self):
        raw = {"prompt_tokens": 0, "completion_tokens": 0}
        result = _normalize_usage(raw, 300, "hello")
        # Should use fallback
        assert result["prompt_tokens"] > 0

    def test_invalid_data(self):
        raw = {"prompt_tokens": "invalid"}
        result = _normalize_usage(raw, 300, "test")
        assert result["prompt_tokens"] == 100  # fallback


class TestDispatch:
    @pytest.mark.asyncio
    async def test_no_candidates_error(self):
        mock_registry = AsyncMock()
        mock_registry.get_candidates = AsyncMock(return_value=[])
        mock_registry.ensure_candidates = AsyncMock()
        mock_registry.selector = AsyncMock()

        from src.core.errors import NoCandidateError
        with pytest.raises(NoCandidateError, match="无候选项"):
            chunks = []
            async for chunk in dispatch(
                mock_registry,
                [{"role": "user", "content": "test"}],
                "test-model",
                stream=False,
            ):
                chunks.append(chunk)

    @pytest.mark.asyncio
    async def test_single_candidate_mode(self):
        mock_registry = MagicMock()
        mock_candidate = MagicMock()
        mock_candidate.id = "qwen_test123"
        mock_candidate.platform = "qwen"
        mock_candidate.models = ["test-model"]

        mock_registry.get_candidates = AsyncMock(return_value=[mock_candidate])
        mock_registry.ensure_candidates = AsyncMock()
        mock_registry.selector.select = AsyncMock(return_value=[mock_candidate])
        mock_adapter = MagicMock()
        mock_registry.adapter_for = MagicMock(return_value=mock_adapter)

        # Mock adapter.complete to return a simple response
        async def mock_complete(*args, **kwargs):
            yield "Hello"
            yield {"usage": {"prompt_tokens": 10, "completion_tokens": 5}}

        mock_adapter.complete = mock_complete
        mock_registry.selector.record = AsyncMock()

        chunks = []
        async for chunk in dispatch(
            mock_registry,
            [{"role": "user", "content": "test"}],
            "test-model",
            stream=False,
        ):
            chunks.append(chunk)

        assert len(chunks) >= 2  # At least text + usage
        mock_registry.adapter_for.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_with_tools_disables_thinking(self):
        mock_registry = MagicMock()
        mock_candidate = MagicMock()
        mock_candidate.id = "qwen_test123"
        mock_candidate.platform = "qwen"
        mock_candidate.models = ["test-model"]

        mock_registry.get_candidates = AsyncMock(return_value=[mock_candidate])
        mock_registry.ensure_candidates = AsyncMock()
        mock_registry.selector.select = AsyncMock(return_value=[mock_candidate])
        mock_adapter = MagicMock()
        mock_registry.adapter_for = MagicMock(return_value=mock_adapter)

        async def mock_complete(*args, **kwargs):
            # Verify thinking is False when tools are provided
            assert kwargs.get("thinking") is False
            yield "Response"
            yield {"usage": {"prompt_tokens": 5, "completion_tokens": 3}}

        mock_adapter.complete = mock_complete
        mock_registry.selector.record = AsyncMock()

        chunks = []
        async for chunk in dispatch(
            mock_registry,
            [{"role": "user", "content": "test"}],
            "test-model",
            stream=False,
            tools=[{"name": "test_tool"}],
        ):
            chunks.append(chunk)

        assert any(isinstance(c, dict) and "usage" in c for c in chunks)
