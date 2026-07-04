"""Tests for src/core/dispatch/registry.py."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.dispatch.registry import Registry


class TestRegistryInit:
    @pytest.mark.asyncio
    async def test_init_creates_selector(self):
        registry = Registry()
        assert registry.selector is not None

    @pytest.mark.asyncio
    async def test_adapters_property(self):
        registry = Registry()
        assert isinstance(registry.adapters, dict)


class TestRegistryGetCandidates:
    @pytest.mark.asyncio
    async def test_get_candidates_no_adapters(self):
        registry = Registry()
        candidates = await registry.get_candidates()
        assert candidates == []

    @pytest.mark.asyncio
    async def test_get_candidates_with_model_filter(self):
        registry = Registry()

        # Mock the internal registry's plugins
        mock_adapter = MagicMock()
        mock_adapter.name = "test"

        from src.core.dispatch.candidate import Candidate
        mock_candidate = Candidate(
            id="test_abc123",
            platform="test",
            resource_id="res1",
            models=["qwen-max", "qwen-plus"],
            available=True,
            busy=False,
            chat=True,
        )
        mock_adapter.candidates = AsyncMock(return_value=[mock_candidate])

        # Inject mock adapter into the registry's plugin registry
        registry._registry._plugins["test"] = mock_adapter

        # Filter by model that exists
        candidates = await registry.get_candidates(model="qwen-max")
        assert len(candidates) == 1

        # Filter by model that doesn't exist
        candidates = await registry.get_candidates(model="nonexistent")
        assert candidates == []

    @pytest.mark.asyncio
    async def test_get_candidates_with_capability_filter(self):
        registry = Registry()

        mock_adapter = MagicMock()
        mock_adapter.name = "test"

        from src.core.dispatch.candidate import Candidate
        mock_candidate = Candidate(
            id="test_abc123",
            platform="test",
            resource_id="res1",
            chat=True,
            vision=False,
        )
        mock_adapter.candidates = AsyncMock(return_value=[mock_candidate])

        registry._registry._plugins["test"] = mock_adapter

        candidates = await registry.get_candidates(capability="chat")
        assert len(candidates) == 1

        candidates = await registry.get_candidates(capability="vision")
        assert candidates == []


class TestRegistryAdapterFor:
    def test_adapter_for_existing(self):
        registry = Registry()
        mock_adapter = MagicMock()
        registry._registry._plugins["test"] = mock_adapter

        from src.core.dispatch.candidate import Candidate
        cand = Candidate(id="test_123", platform="test", resource_id="r")
        assert registry.adapter_for(cand) is mock_adapter

    def test_adapter_for_nonexistent(self):
        registry = Registry()
        from src.core.dispatch.candidate import Candidate
        cand = Candidate(id="test_123", platform="unknown", resource_id="r")
        assert registry.adapter_for(cand) is None


class TestRegistryAllModels:
    @pytest.mark.asyncio
    async def test_all_models_no_adapters(self):
        registry = Registry()
        models = await registry.all_models()
        assert models == []

    @pytest.mark.asyncio
    async def test_all_models_with_adapters(self):
        registry = Registry()

        mock_adapter = MagicMock()
        mock_adapter.name = "test"
        mock_adapter.supported_models = ["model-a", "model-b"]
        mock_adapter.default_capabilities = {"chat": True, "vision": False}
        mock_adapter.context_length = 8192

        registry._registry._plugins["test"] = mock_adapter

        models = await registry.all_models()
        assert len(models) == 2
        assert models[0]["owned_by"] == "test"
        assert models[0]["context_length"] == 8192
        assert models[0]["capabilities"]["chat"] is True


class TestRegistryClose:
    @pytest.mark.asyncio
    async def test_close_no_adapters(self):
        registry = Registry()
        await registry.close()  # Should not raise


class TestRegistryReloadPlatform:
    @pytest.mark.asyncio
    async def test_reload_nonexistent_platform(self):
        registry = Registry()
        mock_session = AsyncMock()

        with patch.object(registry._registry, "reload", return_value=False):
            result = await registry.reload_platform("nonexistent", mock_session)
            assert result is False