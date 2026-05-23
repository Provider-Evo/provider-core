from __future__ import annotations

from src.webui.app import create_app
from src.webui.server import ThreadedWebUIServer, WebUIServer


def test_create_webui_app() -> None:
    app = create_app(registry=None)
    assert app is not None


def test_webui_server_classes_exposed() -> None:
    server = WebUIServer(host='127.0.0.1', port=8001)
    threaded_server = ThreadedWebUIServer(host='127.0.0.1', port=8001)
    assert server.host == '127.0.0.1'
    assert threaded_server.host == '127.0.0.1'
