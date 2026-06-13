from __future__ import annotations

from tests.helpers.platform_contract import verify_platform_contract


def test_aitianhu2_mvp_legacy() -> None:
    verify_platform_contract('aitianhu2')
