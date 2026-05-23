from __future__ import annotations

from tests.helpers.platform_contract import verify_platform_contract


def test_codebuddy_mvp() -> None:
    verify_platform_contract('codebuddy')
