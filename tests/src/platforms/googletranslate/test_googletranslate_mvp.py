from __future__ import annotations

from tests.helpers.platform_contract import verify_platform_contract


def test_googletranslate_mvp() -> None:
    verify_platform_contract('googletranslate')
