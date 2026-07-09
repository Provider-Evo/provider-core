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


def _deepseek_persist_dir_patch(tmp_path: Path):
    from unittest.mock import patch

    def _fake_persist_dir(platform: str) -> Path:
        return tmp_path / platform

    return patch("src.platforms.deepseek.core.modelcache.persist_dir", _fake_persist_dir)


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


class TestDeepSeekModelsCache:
    """Tests for the DeepSeek standalone ModelsCache."""

    def test_init_with_fallback(self):
        """DeepSeek ModelsCache initializes with fallback models."""
        from src.platforms.deepseek.core.modelcache import ModelsCache

        cache = ModelsCache(
            platform="deepseek_test",
            fallback_models=["ds-model-1", "ds-model-2"],
            fetch_enabled=False,
        )
        assert "ds-model-1" in cache.models
        assert "ds-model-2" in cache.models

    @pytest.mark.asyncio
    async def test_load_from_cache_file(self, tmp_path):
        """load() reads models from cache file."""
        from src.platforms.deepseek.core.modelcache import ModelsCache

        cache_dir = tmp_path / "deepseek_load"
        cache_dir.mkdir(parents=True)
        cache_file = cache_dir / "models.json"
        cache_file.write_text(
            json.dumps({"models": ["remote-1", "remote-2"], "updated_at": 12345}),
            encoding="utf-8",
        )

        with _deepseek_persist_dir_patch(tmp_path):
            cache = ModelsCache(
                platform="deepseek_load",
                fallback_models=["fallback"],
                fetch_enabled=False,
            )
            result = await cache.load()
            assert "remote-1" in result
            assert "remote-2" in result

    @pytest.mark.asyncio
    async def test_load_returns_fallback_on_missing_file(self, tmp_path):
        """load() returns fallback when no cache file exists."""
        from src.platforms.deepseek.core.modelcache import ModelsCache

        with _deepseek_persist_dir_patch(tmp_path):
            cache = ModelsCache(
                platform="nonexistent_ds",
                fallback_models=["fb-1"],
                fetch_enabled=False,
            )
            result = await cache.load()
            assert "fb-1" in result

    @pytest.mark.asyncio
    async def test_save_creates_file(self, tmp_path):
        """save() creates the cache file with correct structure."""
        from src.platforms.deepseek.core.modelcache import ModelsCache

        with _deepseek_persist_dir_patch(tmp_path):
            cache = ModelsCache(
                platform="deepseek_save",
                fallback_models=[],
                fetch_enabled=False,
            )
            await cache.save(["saved-1", "saved-2"])

            cache_file = tmp_path / "deepseek_save" / "models.json"
            assert cache_file.is_file()
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            assert data["models"] == ["saved-1", "saved-2"]
            assert "updated_at" in data

    def test_merge_fetch_enabled_replaces(self):
        """_merge replaces models when fetch_enabled=True."""
        from src.platforms.deepseek.core.modelcache import ModelsCache

        cache = ModelsCache(
            platform="merge_replace",
            fallback_models=["old-1"],
            fetch_enabled=True,
        )
        result = cache._merge(["new-1", "new-2"])
        assert result == ["new-1", "new-2"]

    def test_merge_fetch_disabled_adds_only(self):
        """_merge only adds new models when fetch_enabled=False."""
        from src.platforms.deepseek.core.modelcache import ModelsCache

        cache = ModelsCache(
            platform="merge_add",
            fallback_models=["existing-1"],
            fetch_enabled=False,
        )
        result = cache._merge(["existing-1", "new-added"])
        assert "existing-1" in result
        assert "new-added" in result
        assert len(result) == 2

    def test_merge_fetch_disabled_deduplicates(self):
        """_merge does not duplicate existing models."""
        from src.platforms.deepseek.core.modelcache import ModelsCache

        cache = ModelsCache(
            platform="merge_dedup",
            fallback_models=["a", "b"],
            fetch_enabled=False,
        )
        result = cache._merge(["a", "b", "c"])
        assert result.count("a") == 1
        assert result.count("b") == 1
        assert "c" in result

    @pytest.mark.asyncio
    async def test_do_refresh_calls_fetch_and_saves(self, tmp_path):
        """_do_refresh calls fetch_fn, merges, and saves."""
        from src.platforms.deepseek.core.modelcache import ModelsCache

        with _deepseek_persist_dir_patch(tmp_path):
            cache = ModelsCache(
                platform="refresh_test",
                fallback_models=["fallback"],
                fetch_enabled=True,
            )

            async def fake_fetch():
                return ["fetched-1", "fetched-2"]

            await cache._do_refresh(fake_fetch)
            assert "fetched-1" in cache.models
            assert "fetched-2" in cache.models

            # Verify file was saved
            cache_file = tmp_path / "refresh_test" / "models.json"
            assert cache_file.is_file()

    @pytest.mark.asyncio
    async def test_do_refresh_skips_if_already_refreshing(self, tmp_path):
        """_do_refresh skips if a refresh is already in progress."""
        from src.platforms.deepseek.core.modelcache import ModelsCache

        with _deepseek_persist_dir_patch(tmp_path):
            cache = ModelsCache(
                platform="skip_test",
                fallback_models=["fb"],
                fetch_enabled=True,
            )
            cache._refreshing = True  # Simulate in-progress refresh

            call_count = 0

            async def counting_fetch():
                nonlocal call_count
                call_count += 1
                return ["new"]

            await cache._do_refresh(counting_fetch)
            assert call_count == 0  # Should not have been called

    @pytest.mark.asyncio
    async def test_do_refresh_calls_on_update(self, tmp_path):
        """_do_refresh calls on_update callback with merged models."""
        from src.platforms.deepseek.core.modelcache import ModelsCache

        with _deepseek_persist_dir_patch(tmp_path):
            cache = ModelsCache(
                platform="callback_test",
                fallback_models=[],
                fetch_enabled=True,
            )

            updated_models = []

            async def on_update(models):
                updated_models.extend(models)

            async def fake_fetch():
                return ["cb-1", "cb-2"]

            await cache._do_refresh(fake_fetch, on_update=on_update)
            assert "cb-1" in updated_models
            assert "cb-2" in updated_models

    @pytest.mark.asyncio
    async def test_do_refresh_handles_fetch_exception(self, tmp_path):
        """_do_refresh handles exceptions from fetch_fn gracefully."""
        from src.platforms.deepseek.core.modelcache import ModelsCache

        with _deepseek_persist_dir_patch(tmp_path):
            cache = ModelsCache(
                platform="error_test",
                fallback_models=["safe"],
                fetch_enabled=True,
            )

            async def failing_fetch():
                raise RuntimeError("network error")

            # Should not raise
            await cache._do_refresh(failing_fetch)
            # Fallback should still be in models
            assert "safe" in cache.models

    def test_models_property_returns_copy(self):
        """models property returns a copy, not the internal list."""
        from src.platforms.deepseek.core.modelcache import ModelsCache

        cache = ModelsCache(
            platform="copy_test",
            fallback_models=["x"],
            fetch_enabled=False,
        )
        result = cache.models
        result.append("hacked")
        assert "hacked" not in cache.models
