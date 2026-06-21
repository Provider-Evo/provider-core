from __future__ import annotations

import asyncio

from src.core.dispatch.runtime_view import build_runtime_summary


class _FakeCandidate:
    def __init__(self, available: bool, busy: bool) -> None:
        self.available = available
        self.busy = busy


class _FakeAdapter:
    def __init__(self) -> None:
        self.supported_models = ["demo-model"]
        self.default_capabilities = {"chat": True}
        self.context_length = 4096

    async def candidates(self):
        return [_FakeCandidate(True, False), _FakeCandidate(True, True)]


class _FakeSelector:
    async def get_stats(self):
        return {"demo": True}


class _FakeRegistry:
    def __init__(self) -> None:
        self.adapters = {"demo": _FakeAdapter()}
        self.selector = _FakeSelector()

    async def all_models(self):
        return [{"id": "demo-model", "owned_by": "demo", "capabilities": {"chat": True}}]


def test_build_runtime_summary() -> None:
    summary = asyncio.run(build_runtime_summary(_FakeRegistry()))
    assert summary["service"] == "Provider-V2"
    assert summary["counts"]["platforms"] == 1
    assert summary["counts"]["models"] == 1
    assert summary["platforms"]["demo"]["available"] == 1
