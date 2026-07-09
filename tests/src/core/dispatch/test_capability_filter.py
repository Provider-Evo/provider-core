"""Tests for capability_for_model and filter_candidates_by_capability."""

from __future__ import annotations

from src.core.dispatch.candidate import (
    Candidate,
    capability_for_model,
    filter_candidates_by_capability,
    make_id,
    messages_require_capability,
)


def test_capability_for_model_known_and_unknown() -> None:
    cand = Candidate(
        id=make_id("ollama", "srv"),
        platform="ollama",
        resource_id="srv",
        models=["llama3", "llava"],
        meta={
            "model_capabilities": {
                "llama3": {"chat": True},
                "llava": {"chat": True, "vision": True},
            }
        },
        chat=True,
    )
    assert capability_for_model(cand, "llama3", "vision") is False
    assert capability_for_model(cand, "llava", "vision") is True
    assert capability_for_model(cand, "unknown-model", "vision") is None


def test_filter_unknown_capability_treated_as_sufficient() -> None:
    unknown = Candidate(
        id=make_id("ollama", "u"),
        platform="ollama",
        resource_id="u",
        models=["m"],
        meta={},
        chat=True,
    )
    text_only = Candidate(
        id=make_id("ollama", "t"),
        platform="ollama",
        resource_id="t",
        models=["m"],
        meta={"model_capabilities": {"m": {"chat": True}}},
        chat=True,
    )
    out = filter_candidates_by_capability([text_only, unknown], "m", "vision")
    assert unknown in out
    assert text_only not in out


def test_filter_fallback_when_all_known_lack_capability() -> None:
    text_only = Candidate(
        id=make_id("ollama", "t"),
        platform="ollama",
        resource_id="t",
        models=["m"],
        meta={"model_capabilities": {"m": {"chat": True}}},
        chat=True,
    )
    out = filter_candidates_by_capability([text_only], "m", "vision")
    assert out == [text_only]


def test_messages_require_vision() -> None:
    assert messages_require_capability(
        [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "x"}}]}],
        "vision",
    )
    assert not messages_require_capability(
        [{"role": "user", "content": "hello"}],
        "vision",
    )
