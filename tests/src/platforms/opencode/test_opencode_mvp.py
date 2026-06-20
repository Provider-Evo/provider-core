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
    from src.platforms.opencode.core.proxyscore import ProxyPoolSelector
    persist = str(tmp_path / "test_score.json")
    selector = ProxyPoolSelector(persist)
    selector.update_pool(["1.2.3.4:8080", "5.6.7.8:3128"])
    selector.record_success("1.2.3.4:8080", latency_ms=100.0)
    selector.record_failure("5.6.7.8:3128")
    chosen = selector.select(["1.2.3.4:8080", "5.6.7.8:3128"])
    assert chosen in ("1.2.3.4:8080", "5.6.7.8:3128")


def test_proxy_pool_selector_empty() -> None:
    from src.platforms.opencode.core.proxyscore import ProxyPoolSelector
    import tempfile
    import os
    fd, persist = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        selector = ProxyPoolSelector(persist)
        assert selector.select([]) is None
        assert selector.select(["1.2.3.4:8080"]) == "1.2.3.4:8080"
    finally:
        if os.path.exists(persist):
            os.unlink(persist)
