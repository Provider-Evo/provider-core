"""Tests for context_for_model and filter_candidates_by_context."""

from __future__ import annotations

from src.core.dispatch.candidate import (
    Candidate,
    context_for_model,
    filter_candidates_by_context,
    make_id,
)


def test_context_for_model_from_meta() -> None:
    cand = Candidate(
        id=make_id("ollama", "1.2.3.4:11434"),
        platform="ollama",
        resource_id="1.2.3.4:11434",
        models=["llama3"],
        context_length=8192,
        meta={"model_context": {"llama3": 4096}},
        chat=True,
    )
    assert context_for_model(cand, "llama3") == 4096


def test_filter_candidates_by_context() -> None:
    small = Candidate(
        id=make_id("ollama", "a"),
        platform="ollama",
        resource_id="a",
        models=["m"],
        meta={"model_context": {"m": 4096}},
        chat=True,
    )
    large = Candidate(
        id=make_id("ollama", "b"),
        platform="ollama",
        resource_id="b",
        models=["m"],
        meta={"model_context": {"m": 32768}},
        chat=True,
    )
    out = filter_candidates_by_context([small, large], "m", 8000)
    assert out == [large]


def test_filter_unknown_context_treated_as_sufficient() -> None:
    unknown = Candidate(
        id=make_id("ollama", "u"),
        platform="ollama",
        resource_id="u",
        models=["m"],
        meta={},
        chat=True,
    )
    small = Candidate(
        id=make_id("ollama", "s"),
        platform="ollama",
        resource_id="s",
        models=["m"],
        meta={"model_context": {"m": 4096}},
        chat=True,
    )
    out = filter_candidates_by_context([small, unknown], "m", 8000)
    assert unknown in out
    assert small not in out


def test_filter_fallback_when_all_known_insufficient() -> None:
    small = Candidate(
        id=make_id("ollama", "s"),
        platform="ollama",
        resource_id="s",
        models=["m"],
        meta={"model_context": {"m": 4096}},
        chat=True,
    )
    out = filter_candidates_by_context([small], "m", 8000)
    assert out == [small]
