"""Tests for core.models_cache — ModelsCache and global singleton factory."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _persist_dir_patch(tmp_path: Path):
    from unittest.mock import patch

    def _fake_persist_dir(*parts: str) -> Path:
        return tmp_path.joinpath(*parts)

    return patch("src.core.utils.compat.models_cache._persist_dir", _fake_persist_dir)


class TestModelsCache:
    """Tests for the core ModelsCache class."""

    def test_init_with_platform_and_fallback(self):
        """ModelsCache initializes with platform name and fallback models."""
        from src.core.utils.compat.models_cache import ModelsCache

        cache = ModelsCache(
            platform="test_platform",
            fallback_models=["model-a", "model-b"],
            fetch_enabled=False,
        )
        assert isinstance(cache.models, list)
        assert "model-a" in cache.models
        assert "model-b" in cache.models

    def test_models_property_returns_list(self):
        """models property returns a list type."""
        from src.core.utils.compat.models_cache import ModelsCache

        cache = ModelsCache(
            platform="test_prop",
            fallback_models=["m1"],
            fetch_enabled=False,
        )
        result = cache.models
        assert isinstance(result, list)

    def test_fallback_used_when_no_cache_file(self, tmp_path):
        """When no cache file exists, fallback models are returned."""
        from src.core.utils.compat.models_cache import ModelsCache

        with _persist_dir_patch(tmp_path):
            cache = ModelsCache(
                platform="nonexistent",
                fallback_models=["fallback-1", "fallback-2"],
                fetch_enabled=False,
            )
            assert "fallback-1" in cache.models
            assert "fallback-2" in cache.models

    def test_init_starts_with_fallback_even_with_cache_file(self, tmp_path):
        """ListCache.__init__ does NOT read cache file — always starts with fallback."""
        from src.core.utils.compat.models_cache import ModelsCache

        cache_dir = tmp_path / "cached_platform"
        cache_dir.mkdir(parents=True)
        cache_file = cache_dir / "models.json"
        cache_file.write_text(
            json.dumps({"models": ["cached-1", "cached-2", "cached-3"]}),
            encoding="utf-8",
        )

        with _persist_dir_patch(tmp_path):
            cache = ModelsCache(
                platform="cached_platform",
                fallback_models=["fallback"],
                fetch_enabled=True,
            )
            # ListCache.__init__ only uses fallback; cache file requires explicit load()
            assert "fallback" in cache.models
            assert "cached-1" not in cache.models

    @pytest.mark.asyncio
    async def test_load_reads_cache_file(self, tmp_path):
        """Explicit load() reads models from cache file."""
        from src.core.utils.compat.models_cache import ModelsCache

        cache_dir = tmp_path / "load_platform"
        cache_dir.mkdir(parents=True)
        cache_file = cache_dir / "models.json"
        cache_file.write_text(
            json.dumps({"models": ["cached-1", "cached-2", "cached-3"]}),
            encoding="utf-8",
        )

        with _persist_dir_patch(tmp_path):
            cache = ModelsCache(
                platform="load_platform",
                fallback_models=["fallback"],
                fetch_enabled=True,
            )
            # Before load: fallback
            assert "fallback" in cache.models
            # After load: cache file content
            await cache.load()
            assert "cached-1" in cache.models
            assert "cached-2" in cache.models
            assert "cached-3" in cache.models

    def test_fetch_disabled_uses_fallback_even_with_cache(self, tmp_path):
        """With fetch_enabled=False, fallback is used regardless of cache file."""
        from src.core.utils.compat.models_cache import ModelsCache

        cache_dir = tmp_path / "cached_only"
        cache_dir.mkdir(parents=True)
        cache_file = cache_dir / "models.json"
        cache_file.write_text(
            json.dumps({"models": ["old-1"]}),
            encoding="utf-8",
        )

        with _persist_dir_patch(tmp_path):
            cache = ModelsCache(
                platform="cached_only",
                fallback_models=["fb-1", "fb-2"],
                fetch_enabled=False,
            )
            assert "fb-1" in cache.models
            assert "fb-2" in cache.models

    def test_empty_platform_uses_empty_cache_path(self):
        """Empty platform string results in empty cache path."""
        from src.core.utils.compat.models_cache import ModelsCache

        cache = ModelsCache(
            platform="",
            fallback_models=["m1"],
            fetch_enabled=False,
        )
        # Should still work, just no file persistence
        assert isinstance(cache.models, list)

    def test_fetch_enabled_true_overwrite(self):
        """fetch_enabled=True enables overwrite mode."""
        from src.core.utils.compat.models_cache import ModelsCache

        cache = ModelsCache(
            platform="overwrite_test",
            fallback_models=["f1"],
            fetch_enabled=True,
        )
        # Should not crash, overwrite is enabled
        assert isinstance(cache.models, list)


class TestModelsFactory:
    """Tests for the models() global singleton factory."""

    def test_models_returns_models_cache_instance(self):
        """models() returns a ModelsCache instance."""
        from src.core.utils.compat.models_cache import ModelsCache, models

        instance = models()
        assert isinstance(instance, ModelsCache)

    def test_models_returns_same_instance(self):
        """Multiple calls to models() return the same instance."""
        from src.core.utils.compat.models_cache import models

        instance1 = models()
        instance2 = models()
        assert instance1 is instance2
