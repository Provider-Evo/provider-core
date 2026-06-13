"""Tests for src/core/dispatch/candidate.py."""

import pytest

from src.core.dispatch.candidate import Candidate, make_id, ALL_CAPABILITIES


class TestCandidate:
    def test_default_values(self):
        c = Candidate(id="qwen_abc123", platform="qwen", resource_id="user1")
        assert c.available is True
        assert c.busy is False
        assert c.context_length is None
        assert c.models == []
        assert c.meta == {}
        # All capabilities default to False
        for cap in ALL_CAPABILITIES:
            assert getattr(c, cap) is False, f"{cap} should be False by default"

    def test_has_capability_true(self):
        c = Candidate(id="qwen_abc", platform="qwen", resource_id="u", chat=True, vision=True)
        assert c.has_capability("chat") is True
        assert c.has_capability("vision") is True

    def test_has_capability_false(self):
        c = Candidate(id="qwen_abc", platform="qwen", resource_id="u")
        assert c.has_capability("chat") is False
        assert c.has_capability("video_gen") is False

    def test_has_capability_unknown(self):
        c = Candidate(id="qwen_abc", platform="qwen", resource_id="u")
        assert c.has_capability("nonexistent") is False

    def test_to_model_dict_basic(self):
        c = Candidate(id="qwen_abc", platform="qwen", resource_id="u", chat=True, tools=True)
        d = c.to_model_dict()
        assert d["object"] == "model"
        assert d["owned_by"] == "qwen"
        assert d["capabilities"]["chat"] is True
        assert d["capabilities"]["tools"] is True
        assert "video_gen" not in d["capabilities"]

    def test_to_model_dict_owned_by_override(self):
        c = Candidate(id="qwen_abc", platform="qwen", resource_id="u", chat=True)
        d = c.to_model_dict(owned_by="custom")
        assert d["owned_by"] == "custom"

    def test_to_model_dict_context_length(self):
        c = Candidate(id="qwen_abc", platform="qwen", resource_id="u", context_length=32000)
        d = c.to_model_dict()
        assert d["context_length"] == 32000

    def test_to_model_dict_no_context_length(self):
        c = Candidate(id="qwen_abc", platform="qwen", resource_id="u")
        d = c.to_model_dict()
        assert "context_length" not in d

    def test_all_capabilities_in_model_dict(self):
        c = Candidate(id="qwen_abc", platform="qwen", resource_id="u")
        # Set all capabilities to True
        for cap in ALL_CAPABILITIES:
            setattr(c, cap, True)
        d = c.to_model_dict()
        for cap in ALL_CAPABILITIES:
            assert d["capabilities"][cap] is True


class TestMakeId:
    def test_format_with_resource_id(self):
        mid = make_id("qwen", "user123")
        assert mid.startswith("qwen_")
        parts = mid.split("_", 1)
        assert len(parts[1]) == 12  # hash12

    def test_deterministic(self):
        id1 = make_id("qwen", "user123")
        id2 = make_id("qwen", "user123")
        assert id1 == id2

    def test_different_resource_ids(self):
        id1 = make_id("qwen", "user1")
        id2 = make_id("qwen", "user2")
        assert id1 != id2

    def test_fallback_without_resource_id(self):
        mid = make_id("qwen")
        assert mid.startswith("qwen_")
        parts = mid.split("_", 1)
        assert len(parts[1]) == 12  # hex12

    def test_uniqueness_fallback(self):
        ids = {make_id("qwen") for _ in range(100)}
        assert len(ids) == 100  # All unique (random UUID)

    def test_different_platforms(self):
        id1 = make_id("qwen", "user1")
        id2 = make_id("ollama", "user1")
        assert id1.startswith("qwen_")
        assert id2.startswith("ollama_")
        assert id1 != id2
