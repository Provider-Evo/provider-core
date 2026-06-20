from __future__ import annotations

from tests.helpers.platform_contract import verify_platform_contract


def test_opencode_mvp() -> None:
    verify_platform_contract('opencode')


def test_opencode_name() -> None:
    from src.platforms.opencode import Adapter
    adapter = Adapter()
    assert adapter.name == "opencode"


def test_opencode_supported_models() -> None:
    from src.platforms.opencode import Adapter
    from src.platforms.opencode.core.constants import MODELS
    adapter = Adapter()
    assert adapter.supported_models == list(MODELS)


def test_opencode_default_capabilities() -> None:
    from src.platforms.opencode import Adapter
    from src.platforms.opencode.core.constants import CAPS
    adapter = Adapter()
    assert adapter.default_capabilities == CAPS


def test_opencode_caps_native_tools() -> None:
    from src.platforms.opencode.core.constants import CAPS
    assert CAPS.get("native_tools") is True
    assert CAPS.get("chat") is True
    assert CAPS.get("tools") is True


def test_proxy_info_dataclass() -> None:
    from src.platforms.opencode.core.proxypool import ProxyInfo
    p = ProxyInfo(ip="1.2.3.4", port=8080, protocol="http")
    assert p.address == "1.2.3.4:8080"
    assert hash(p) == hash("1.2.3.4:8080")
    p2 = ProxyInfo(ip="1.2.3.4", port=8080)
    assert p == p2


def test_proxy_pool_dedup() -> None:
    from src.platforms.opencode.core.proxypool import ProxyInfo, ProxyPool
    pool = ProxyPool()
    p1 = ProxyInfo(ip="1.2.3.4", port=8080)
    p2 = ProxyInfo(ip="1.2.3.4", port=8080)
    p3 = ProxyInfo(ip="5.6.7.8", port=3128)
    pool.add(p1)
    pool.add(p2)
    pool.add(p3)
    assert pool.count == 2
    assert pool.to_address_list() == ["1.2.3.4:8080", "5.6.7.8:3128"]


def test_proxy_pool_serialization() -> None:
    from src.platforms.opencode.core.proxypool import ProxyInfo, ProxyPool
    pool = ProxyPool(fetch_time="2026-06-20T00:00:00Z", total_available=100)
    pool.add(ProxyInfo(ip="1.2.3.4", port=8080, protocol="http", country="US"))
    data = pool.to_dict()
    assert data["fetch_time"] == "2026-06-20T00:00:00Z"
    assert len(data["proxies"]) == 1
    restored = ProxyPool.from_dict(data)
    assert restored.count == 1
    assert restored.proxies[0].address == "1.2.3.4:8080"
    assert restored.fetch_time == "2026-06-20T00:00:00Z"


def test_proxy_pool_selector_scoring(tmp_path) -> None:
    from src.platforms.opencode.core.proxyscore import DIRECT, ProxyPoolSelector
    persist = str(tmp_path / "test_score.json")
    selector = ProxyPoolSelector(persist)
    selector.update_pool(["1.2.3.4:8080", "5.6.7.8:3128"])
    selector.record_success("1.2.3.4:8080", latency_ms=100.0)
    selector.record_failure("5.6.7.8:3128")
    chosen = selector.select(["1.2.3.4:8080", "5.6.7.8:3128"])
    assert chosen in ("1.2.3.4:8080", "5.6.7.8:3128", DIRECT)


def test_proxy_pool_selector_empty() -> None:
    from src.platforms.opencode.core.proxyscore import DIRECT, ProxyPoolSelector
    import tempfile
    import os
    fd, persist = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        selector = ProxyPoolSelector(persist)
        # select([]) now returns DIRECT since DIRECT is always a candidate
        assert selector.select([]) == DIRECT
        # select with one proxy: could return the proxy or DIRECT
        assert selector.select(["1.2.3.4:8080"]) in ("1.2.3.4:8080", DIRECT)
    finally:
        if os.path.exists(persist):
            os.unlink(persist)


def test_direct_constant_value() -> None:
    from src.platforms.opencode.core.proxyscore import DIRECT
    assert DIRECT == "direct"


def test_direct_in_score_table_after_update_pool(tmp_path) -> None:
    from src.platforms.opencode.core.proxyscore import DIRECT, ProxyPoolSelector
    persist = str(tmp_path / "test_score.json")
    selector = ProxyPoolSelector(persist)
    selector.update_pool(["1.2.3.4:8080", "5.6.7.8:3128"])
    # DIRECT must always be present in the score table
    assert DIRECT in selector._scores


def test_direct_survives_stale_cleanup(tmp_path) -> None:
    from src.platforms.opencode.core.proxyscore import DIRECT, ProxyPoolSelector
    persist = str(tmp_path / "test_score.json")
    selector = ProxyPoolSelector(persist)
    # First update: add two proxies + DIRECT
    selector.update_pool(["1.2.3.4:8080", "5.6.7.8:3128"])
    assert "1.2.3.4:8080" in selector._scores
    assert "5.6.7.8:3128" in selector._scores
    assert DIRECT in selector._scores
    # Second update: remove both proxies, DIRECT should survive
    selector.update_pool([])
    assert "1.2.3.4:8080" not in selector._scores
    assert "5.6.7.8:3128" not in selector._scores
    assert DIRECT in selector._scores


def test_direct_record_success_and_failure(tmp_path) -> None:
    from src.platforms.opencode.core.proxyscore import DIRECT, ProxyPoolSelector
    persist = str(tmp_path / "test_score.json")
    selector = ProxyPoolSelector(persist)
    selector.update_pool([])
    # record_success for DIRECT
    selector.record_success(DIRECT, latency_ms=200.0)
    rec = selector._scores[DIRECT]
    assert rec.n_fails == 0
    assert rec.n_calls == 1
    assert rec.ema_latency == 200.0
    # record_failure for DIRECT
    selector.record_failure(DIRECT)
    assert rec.n_fails == 1
    # another success resets failure count
    selector.record_success(DIRECT, latency_ms=300.0)
    assert rec.n_fails == 0
    assert rec.n_calls == 2


def test_direct_can_be_selected(tmp_path) -> None:
    from src.platforms.opencode.core.proxyscore import DIRECT, ProxyPoolSelector
    persist = str(tmp_path / "test_score.json")
    selector = ProxyPoolSelector(persist)
    selector.update_pool([])
    # With no proxies, select should return DIRECT
    assert selector.select([]) == DIRECT


def test_single_candidate_model() -> None:
    """Verify the single-candidate model: one candidate when pool has proxies."""
    import asyncio
    from src.platforms.opencode.core.client import OpencodeClient
    from src.platforms.opencode.core.proxypool import ProxyInfo, ProxyPool

    client = OpencodeClient()
    # Empty pool -> no candidates
    result = asyncio.run(client.candidates())
    assert result == []

    # Simulate a non-empty pool
    pool = ProxyPool()
    pool.add(ProxyInfo(ip="1.2.3.4", port=8080, protocol="http"))
    pool.add(ProxyInfo(ip="5.6.7.8", port=3128, protocol="https"))
    client._pool = pool
    client._selector.update_pool(pool.to_address_list())

    result = asyncio.run(client.candidates())
    assert len(result) == 1
    c = result[0]
    assert c.platform == "opencode"
    assert c.resource_id == "proxy-pool"
    assert c.meta["proxy_addr"] == ""
