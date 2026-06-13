from __future__ import annotations

from unittest import mock

from src.platforms.ollama.core.discover import _parse_ips, collect_servers


def test_parse_ips() -> None:
    html = """
    <button onclick="copyToClipboard('192.168.1.1:11434')"></button>
    <button onclick="copyToClipboard('192.168.1.2:11434')"></button>
    """
    ips = _parse_ips(html)
    assert ips == ["192.168.1.1:11434", "192.168.1.2:11434"]


def test_collect_servers_without_network_failure() -> None:
    with mock.patch(
        'src.platforms.ollama.core.discover._fetch_page',
        return_value=None,
    ):
        servers = collect_servers(additional=['192.168.1.100:11434'])
    assert isinstance(servers, dict)
