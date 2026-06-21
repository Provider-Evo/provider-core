from __future__ import annotations

from src.core.server import PortReleaseResult


def test_port_release_result_fields() -> None:
    result = PortReleaseResult(
        port=1337,
        occupied=True,
        released=True,
        pids=[1, 2],
        detail='ok',
    )
    assert result.port == 1337
    assert result.occupied is True
    assert result.released is True
    assert result.pids == [1, 2]
