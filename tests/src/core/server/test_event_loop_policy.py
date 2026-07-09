from __future__ import annotations

import sys
from unittest.mock import patch

from src.core.server.infra import event_loop_policy
from src.core.server.lifecycle.runner import _describe_exit_code


def test_describe_exit_code_sigsegv() -> None:
    text = _describe_exit_code(-11)
    assert "SIGSEGV" in text
    assert "-11" in text


def test_py314_skips_uvloop_by_default(monkeypatch) -> None:
    """Python 3.14 默认不启用 uvloop，避免 SIGSEGV。"""
    monkeypatch.delenv("PROVIDER_USE_UVLOOP", raising=False)
    with patch.object(event_loop_policy.sys, "version_info", (3, 14, 6)):
        with patch.object(event_loop_policy.sys, "platform", "linux"):
            with patch.object(event_loop_policy.logger, "info") as info_log:
                event_loop_policy.configure_event_loop_policy()
    assert any("禁用 uvloop" in str(call.args[0]) for call in info_log.call_args_list)


def test_py314_uvloop_requires_min_version(monkeypatch) -> None:
    """Python 3.14 显式开启时仍要求 uvloop>=0.22.1。"""
    monkeypatch.setenv("PROVIDER_USE_UVLOOP", "1")
    fake_uvloop = type(sys)("uvloop")
    with patch.object(event_loop_policy.sys, "version_info", (3, 14, 6)):
        with patch.object(event_loop_policy.sys, "platform", "linux"):
            with patch.dict(event_loop_policy.sys.modules, {"uvloop": fake_uvloop}):
                with patch(
                    "src.core.server.infra.event_loop_policy._uvloop_version",
                    return_value=(0, 21, 0),
                ):
                    with patch.object(event_loop_policy.logger, "warning") as warn_log:
                        event_loop_policy.configure_event_loop_policy()
    assert any("需要 uvloop>=" in str(call.args[0]) for call in warn_log.call_args_list)
