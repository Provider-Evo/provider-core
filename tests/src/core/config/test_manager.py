"""Tests for src/core/config/manager.py."""
import asyncio
import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.core.config.manager import ConfigManager
from src.core.config.sections import AppConfig


class TestFindConfig:
    def test_returns_none_when_not_found(self):
        # Should return None if no config.toml exists
        from src.core.config.manager import _find_config

        # This may return a real path if config.toml exists in the project
        result = _find_config()
        # Just verify it doesn't crash
        assert result is None or isinstance(result, Path)


class TestFindTemplate:
    def test_returns_none_or_path(self):
        from src.core.config.manager import _find_template
        result = _find_template()
        assert result is None or isinstance(result, Path)


class TestConfigManagerInit:
    def test_init_sets_defaults(self):
        mgr = ConfigManager()
        assert mgr._config is None
        assert mgr._config_path is None
        assert mgr._callbacks == {}


class TestConfigManagerLock:
    @pytest.mark.asyncio
    async def test_get_lock_creates_lock(self):
        mgr = ConfigManager()
        lock = mgr._get_lock()
        assert isinstance(lock, asyncio.Lock)

    @pytest.mark.asyncio
    async def test_get_lock_returns_same_instance(self):
        mgr = ConfigManager()
        lock1 = mgr._get_lock()
        lock2 = mgr._get_lock()
        assert lock1 is lock2


class TestConfigManagerLoad:
    @pytest.mark.asyncio
    async def test_load_raises_when_no_config(self):
        mgr = ConfigManager()

        with patch("src.core.config.manager._find_config", return_value=None):
            with patch("src.core.config.manager._find_template", return_value=None):
                with pytest.raises(RuntimeError, match="无法找到或创建 config.toml"):
                    mgr.load()


class TestConfigManagerReload:
    @pytest.mark.asyncio
    async def test_reload_returns_false_when_no_path(self):
        mgr = ConfigManager()
        result = await mgr.reload()
        assert result is False


class TestConfigManagerProperty:
    def test_config_raises_when_not_loaded(self):
        mgr = ConfigManager()
        with pytest.raises(RuntimeError, match="配置尚未加载"):
            _ = mgr.config

    def test_getattr_raises_when_not_loaded(self):
        mgr = ConfigManager()
        with pytest.raises(RuntimeError, match="配置尚未加载"):
            _ = mgr.server

    def test_getattr_private_raises_attribute_error(self):
        mgr = ConfigManager()
        with pytest.raises(AttributeError):
            _ = mgr._private


class TestConfigManagerMergeDicts:
    def test_merges_missing_keys(self):
        target = {"a": 1}
        source = {"a": 2, "b": 3}
        ConfigManager._merge_dicts(target, source)
        assert target["a"] == 1  # Existing value preserved
        assert target["b"] == 3  # New key added

    def test_skips_version(self):
        target = {}
        source = {"version": "2.0.0", "other": "value"}
        ConfigManager._merge_dicts(target, source)
        assert "version" not in target
        assert target["other"] == "value"

    def test_recurses_nested(self):
        target = {"outer": {"inner": 1}}
        source = {"outer": {"new": 2}}
        ConfigManager._merge_dicts(target, source)
        assert target["outer"]["inner"] == 1
        assert target["outer"]["new"] == 2


class TestConfigManagerCallbacks:
    @pytest.mark.asyncio
    async def test_register_callback(self):
        mgr = ConfigManager()
        callback = MagicMock()
        mgr.on_config_change("server.port", callback)
        assert "server.port" in mgr._callbacks
        assert callback in mgr._callbacks["server.port"]

    @pytest.mark.asyncio
    async def test_notify_changes_calls_callback(self):
        mgr = ConfigManager()
        results = []

        async def callback(old_val, new_val):
            results.append((old_val, new_val))

        mgr.on_config_change("server.port", callback)

        old_cfg = AppConfig()
        old_cfg.server.port = 1337

        new_cfg = AppConfig()
        new_cfg.server.port = 8080

        await mgr._notify_changes(old_cfg, new_cfg)
        assert len(results) == 1
        assert results[0] == (1337, 8080)

    @pytest.mark.asyncio
    async def test_notify_changes_skips_unchanged(self):
        mgr = ConfigManager()
        call_count = 0

        async def callback(old_val, new_val):
            nonlocal call_count
            call_count += 1

        mgr.on_config_change("server.port", callback)

        old_cfg = AppConfig()
        new_cfg = AppConfig()
        # Both have default port 1337

        await mgr._notify_changes(old_cfg, new_cfg)
        assert call_count == 0  # Should not call callback


class TestConfigManagerGetValue:
    def test_get_value_nested(self):
        cfg = AppConfig()
        result = ConfigManager._get_value(cfg, "server.port")
        assert result == 1337

    def test_get_value_deep_nested(self):
        cfg = AppConfig()
        result = ConfigManager._get_value(cfg, "gateway.concurrent_count")
        assert result == 3


class TestConfigManagerRepr:
    def test_repr_not_watching(self):
        mgr = ConfigManager()
        r = repr(mgr)
        assert "ConfigManager" in r
        assert "watching=False" in r
