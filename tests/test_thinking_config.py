from __future__ import annotations

from src.routes.shared.thinking import (
    resolve_thinking_config,
    thinking_to_dispatch_kwargs,
)


def test_openai_thinking_bool() -> None:
    cfg = resolve_thinking_config({"thinking": True}, flavor="openai")
    assert cfg.level == "auto"
    assert cfg.mode == "auto"
    assert cfg.enabled is True

    cfg_off = resolve_thinking_config({"thinking": False}, flavor="openai")
    assert cfg_off.level == "none"
    assert cfg_off.mode == "off"
    assert cfg_off.enabled is False


def test_openai_thinking_mode_explicit() -> None:
    cfg = resolve_thinking_config({"thinking_mode": "on"}, flavor="openai")
    assert cfg.level == "medium"
    assert cfg.mode == "on"
    cfg_auto = resolve_thinking_config({"thinking_mode": "auto"}, flavor="openai")
    assert cfg_auto.level == "auto"
    assert cfg_auto.mode == "auto"


def test_openai_reasoning_effort_maps_to_level() -> None:
    cases = {
        "low": "low",
        "medium": "medium",
        "high": "high",
        "xhigh": "xhigh",
        "minimal": "low",
        "max": "max",
        "default": "medium",
        "on": "medium",
    }
    for effort, expected in cases.items():
        cfg = resolve_thinking_config({"reasoning_effort": effort}, flavor="openai")
        assert cfg.level == expected, effort
        assert cfg.mode == "on", effort
        assert cfg.enabled is True


def test_openai_reasoning_effort_off_aliases() -> None:
    for effort in ("none", "off", "false", "disabled", "no"):
        cfg = resolve_thinking_config({"reasoning_effort": effort}, flavor="openai")
        assert cfg.level == "none", effort
        assert cfg.mode == "off", effort
        assert cfg.enabled is False


def test_openai_reasoning_effort_bool_numeric() -> None:
    assert resolve_thinking_config({"reasoning_effort": True}, flavor="openai").level == "medium"
    assert resolve_thinking_config({"reasoning_effort": False}, flavor="openai").level == "none"
    assert resolve_thinking_config({"reasoning_effort": 1}, flavor="openai").level == "medium"
    assert resolve_thinking_config({"reasoning_effort": 0}, flavor="openai").level == "none"


def test_openai_reasoning_object_effort() -> None:
    cfg = resolve_thinking_config({"reasoning": {"effort": "high"}}, flavor="openai")
    assert cfg.level == "high"
    assert cfg.mode == "on"
    assert cfg.enabled is True


def test_openai_reasoning_object_mode() -> None:
    cfg = resolve_thinking_config({"reasoning": {"mode": "auto"}}, flavor="openai")
    assert cfg.level == "auto"
    assert cfg.mode == "auto"


def test_openai_reasoning_object_budget() -> None:
    cfg = resolve_thinking_config(
        {"reasoning": {"effort": "medium", "budget_tokens": 256}},
        flavor="openai",
    )
    assert cfg.level == "medium"
    assert cfg.mode == "on"
    assert cfg.max_tokens == 256


def test_openai_thinking_takes_precedence_over_reasoning_effort() -> None:
    cfg = resolve_thinking_config(
        {"thinking": False, "reasoning_effort": "high"},
        flavor="openai",
    )
    assert cfg.level == "none"
    assert cfg.mode == "off"
    assert cfg.enabled is False


def test_openai_bare_body_no_mode() -> None:
    cfg = resolve_thinking_config({"model": "x", "messages": []}, flavor="openai")
    assert cfg.level is None
    assert cfg.mode is None
    assert cfg.enabled is False


def test_openai_extra_body_reasoning_effort() -> None:
    cfg = resolve_thinking_config(
        {"messages": []},
        extra={"reasoning_effort": "medium"},
        flavor="openai",
    )
    assert cfg.level == "medium"
    assert cfg.mode == "on"


def test_openai_thinking_object_type_enabled() -> None:
    cfg = resolve_thinking_config(
        {"thinking": {"type": "enabled", "budget_tokens": 128}},
        flavor="openai",
    )
    assert cfg.level == "medium"
    assert cfg.mode == "on"
    assert cfg.max_tokens == 128


def test_thinking_to_dispatch_kwargs_from_reasoning_effort() -> None:
    cfg = resolve_thinking_config({"reasoning_effort": "medium"}, flavor="openai")
    kw = thinking_to_dispatch_kwargs(cfg)
    assert kw["thinking"] is True
    assert kw["thinking_level"] == "medium"
    assert kw["thinking_mode"] == "on"


def test_anthropic_thinking_enabled() -> None:
    cfg = resolve_thinking_config(
        {"thinking": {"type": "enabled", "budget_tokens": 256}},
        flavor="anthropic",
    )
    assert cfg.level == "medium"
    assert cfg.mode == "on"
    assert cfg.max_tokens == 256
