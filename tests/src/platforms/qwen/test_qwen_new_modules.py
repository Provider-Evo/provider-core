from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import aiohttp

from src.platforms.qwen.core.bxumid import validate_bxumidtoken
from src.platforms.qwen.core.chat_session import ChatSession
from src.platforms.qwen.core.runtime import Candidate, make_id, ModelsCache, ProxySelector


class TestBxumid:
    def test_validate_bxumidtoken_valid(self) -> None:
        assert validate_bxumidtoken("T2gAabcdefghijklmnopqrst") is True
        assert validate_bxumidtoken("abcdefghijklmnopqrst") is True
        assert validate_bxumidtoken("T2gA" + "A" * 20) is True

    def test_validate_bxumidtoken_invalid(self) -> None:
        assert validate_bxumidtoken("") is False
        assert validate_bxumidtoken("short") is False
        assert validate_bxumidtoken("T2gA") is False
        assert validate_bxumidtoken("invalid!token") is False


class TestChatSession:
    def test_chat_session_init(self) -> None:
        session = MagicMock(spec=aiohttp.ClientSession)
        proxy_resolver = lambda: None
        cookies_provider = lambda: {}
        fingerprint_provider = lambda: "test-fingerprint"
        
        chat_session = ChatSession(session, proxy_resolver, cookies_provider, fingerprint_provider)
        assert chat_session._session is session
        assert chat_session._resolve_proxy is proxy_resolver
        assert chat_session._cookies is cookies_provider
        assert chat_session._fingerprint is fingerprint_provider

    @pytest.mark.asyncio
    async def test_chat_session_stop_returns_false_on_empty_params(self) -> None:
        session = MagicMock(spec=aiohttp.ClientSession)
        chat_session = ChatSession(session, lambda: None, lambda: {}, lambda: "fp")
        
        assert await chat_session.stop("", "token") is False
        assert await chat_session.stop("chat_id", "") is False

    @pytest.mark.asyncio
    async def test_chat_session_delete_returns_false_on_empty_params(self) -> None:
        session = MagicMock(spec=aiohttp.ClientSession)
        chat_session = ChatSession(session, lambda: None, lambda: {}, lambda: "fp")
        
        assert await chat_session.delete("", "token") is False
        assert await chat_session.delete("chat_id", "") is False


class TestRuntime:
    def test_candidate_dataclass(self) -> None:
        candidate = Candidate(
            id="test-id",
            platform="qwen",
            resource_id="resource-1",
            models=["qwen3-max", "qwen3-plus"],
            chat=True,
            vision=True,
        )
        assert candidate.id == "test-id"
        assert candidate.platform == "qwen"
        assert candidate.resource_id == "resource-1"
        assert candidate.models == ["qwen3-max", "qwen3-plus"]
        assert candidate.chat is True
        assert candidate.vision is True
        assert candidate.thinking is False

    def test_make_id(self) -> None:
        assert make_id("qwen", "resource-1") == "qwen:resource-1"
        assert make_id("opencode", "proxy-pool") == "opencode:proxy-pool"

    def test_models_cache_init(self) -> None:
        cache = ModelsCache("qwen", ["qwen3-max", "qwen3-plus"], fetch_enabled=False)
        assert cache.namespace == "qwen"
        assert cache.models == ["qwen3-max", "qwen3-plus"]
        assert cache.fetch_enabled is False

    @pytest.mark.asyncio
    async def test_models_cache_load(self) -> None:
        cache = ModelsCache("qwen", ["qwen3-max"])
        await cache.load()  # Should not raise

    def test_proxy_selector_init(self, tmp_path) -> None:
        selector = ProxySelector(tmp_path / "test_proxy.json")
        assert selector.prefer_proxy is False

    def test_proxy_selector_select(self, tmp_path) -> None:
        selector = ProxySelector(tmp_path / "test_proxy.json")
        assert selector.select() is False

    def test_proxy_selector_record_success(self, tmp_path) -> None:
        selector = ProxySelector(tmp_path / "test_proxy.json")
        selector.record(True, True, 100.0)
        # After successful proxy use with low latency, prefer_proxy should be True
        assert selector.prefer_proxy is True

    def test_proxy_selector_record_failure(self, tmp_path) -> None:
        selector = ProxySelector(tmp_path / "test_proxy.json")
        selector.record(True, False)
        # After failed proxy use, prefer_proxy should be False
        assert selector.prefer_proxy is False
