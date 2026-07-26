from __future__ import annotations

from src.core.dispatch.engine.support.fncall_context import build_entml_protocol_options
from src.routes.shared.thinking import ThinkingConfig, thinking_to_dispatch_kwargs


def test_thinking_to_dispatch_kwargs_includes_interleaved_history() -> None:
    cfg = ThinkingConfig(mode="on", interleaved_history=True)
    kw = thinking_to_dispatch_kwargs(cfg)
    assert kw["thinking"] is True
    assert kw["include_thinking_in_history"] is True
    assert kw["thinking_mode"] == "on"


def test_thinking_to_dispatch_kwargs_interleaved_off() -> None:
    cfg = ThinkingConfig(mode="off", interleaved_history=False)
    kw = thinking_to_dispatch_kwargs(cfg)
    assert kw["thinking"] is False
    assert kw["include_thinking_in_history"] is False
    assert kw["thinking_mode"] == "off"


def test_build_entml_protocol_options_passes_include_thinking_in_history() -> None:
    opts = build_entml_protocol_options(
        thinking=True,
        thinking_mode="on",
        include_thinking_in_history=True,
    )
    assert opts is not None
    assert opts["thinking_mode"] == "on"
    assert opts["include_thinking_in_history"] is True


def test_build_entml_protocol_options_history_only_when_thinking_off() -> None:
    opts = build_entml_protocol_options(
        thinking=False,
        thinking_mode="off",
        include_thinking_in_history=True,
    )
    assert opts == {"include_thinking_in_history": True}
