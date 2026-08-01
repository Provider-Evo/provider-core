from __future__ import annotations

from src.core.dispatch.engine.support.fncall_context import build_entml_protocol_options
from src.routes.shared.thinking import ThinkingConfig, thinking_to_dispatch_kwargs


def test_thinking_to_dispatch_kwargs_includes_interleaved_history() -> None:
    cfg = ThinkingConfig(level="medium", mode="on", interleaved_history=True)
    kw = thinking_to_dispatch_kwargs(cfg)
    assert kw["thinking"] is True
    assert kw["include_thinking_in_history"] is True
    assert kw["thinking_level"] == "medium"
    assert kw["thinking_mode"] == "on"


def test_thinking_to_dispatch_kwargs_interleaved_off() -> None:
    cfg = ThinkingConfig(level="none", mode="off", interleaved_history=False)
    kw = thinking_to_dispatch_kwargs(cfg)
    assert kw["thinking"] is False
    assert kw["include_thinking_in_history"] is False
    assert kw["thinking_level"] == "none"
    assert kw["thinking_mode"] == "off"


def test_build_entml_protocol_options_never_injects_thinking() -> None:
    opts = build_entml_protocol_options(
        thinking=True,
        thinking_level="medium",
        include_thinking_in_history=True,
    )
    assert opts is None
