from __future__ import annotations

from tests.helpers.platform_contract import verify_platform_contract


def test_noobkeys_mvp() -> None:
    """NoobKeys 平台最小契约测试。"""
    verify_platform_contract('noobkeys')
