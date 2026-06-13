"""Tests for src/core/dispatch/registry.py."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.dispatch.registry import Registry


class TestRegistryIsAdapterClass:
    def setup_method(self):
        self.registry = Registry()

    def test_non_class_returns_false(self):
        assert self.registry._is_adapter_class("string") is False
        assert self.registry._is_adapter_class(123) is False

    def test_base_platform_adapter_returns_false(self):
        from src.platforms.base import PlatformAdapter
        assert self.registry._is_adapter_class(PlatformAdapter) is False

    def test_class_without_required_methods_returns_false(self):
        class IncompleteAdapter:
            pass

        IncompleteAdapter.__module__ = "src.platforms.test"
        assert self.registry._is_adapter_class(IncompleteAdapter) is False

    def test_valid_adapter_class(self):
        class MockAdapter:
            def init(self): pass
            def candidates(self): pass
            def ensure_candidates(self): pass
            def complete(self): pass
            def close(self): pass

        MockAdapter.__module__ = "src.platforms.test"
        # Add name property
        MockAdapter.name = property(lambda self: "test")
        assert self.registry._is_adapter_class(MockAdapter) is True


class TestRegistryDiscovery:
    def test_discover_adapter_classes(self):
        registry = Registry()
        # This should not crash even if no adapters exist
        adapters = registry._discover_adapter_classes("src.platforms")
        assert isinstance(adapters, list)

    def test_discover_from_nonexistent_package(self):
        registry = Registry()
        adapters = registry._discover_adapter_classes("nonexistent.package")
        assert adapters == []


class TestRegistryInit:
    @pytest.mark.asyncio
    async def test_init_with_no_adapters(self):
        registry = Registry()
        mock_session = AsyncMock()

        with patch("importlib.import_module", side_effect=ImportError):
            await registry.init(mock_session)

        assert len(registry.adapters) == 0

    @pytest.mark.asyncio
    async def test_init_empty_platforms(self):
        registry = Registry()
        mock_session = AsyncMock()

        # Mock to return no adapters
        with patch.object(registry, "_discover_adapter_classes", return_value=[]):
            await registry.init(mock_session)

        assert len(registry.adapters) == 0


class TestRegistryGetCandidates:
    @pytest.mark.asyncio
    async def test_get_candidates_no_adapters(self):
        registry = Registry()
        candidates = await registry.get_candidates()
        assert candidates == []

    @pytest.mark.asyncio
    async def test_get_candidates_with_model_filter(self):
        registry = Registry()

        # Mock adapter
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

        registry._adapters["test"] = mock_adapter

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

        registry._adapters["test"] = mock_adapter

        candidates = await registry.get_candidates(capability="chat")
        assert len(candidates) == 1

        candidates = await registry.get_candidates(capability="vision")
        assert candidates == []


class TestRegistryAdapterFor:
    def test_adapter_for_existing(self):
        registry = Registry()
        mock_adapter = MagicMock()
        registry._adapters["test"] = mock_adapter

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

        registry._adapters["test"] = mock_adapter

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

        with patch.object(registry, "_discover_adapter_classes", return_value=[]):
            result = await registry.reload_platform("nonexistent", mock_session)
            assert result is False
