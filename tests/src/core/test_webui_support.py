from __future__ import annotations

import json
from pathlib import Path

from src.webui.config_schema import PortableWebUISettings, SummaryExportPayload, WebUIServerConfig
from src.webui.dependencies import get_portable_settings, get_server_config
from src.webui.schemas import summarize_for_client
from src.webui.utils import make_json_download_name


def test_webui_config_models_to_dict() -> None:
    portable = PortableWebUISettings()
    server = WebUIServerConfig(host='127.0.0.1', port=8001)
    export_payload = SummaryExportPayload(service='Provider-V2', version='2.2.0', timestamp=1)
    assert portable.to_dict()['theme'] == 'auto'
    assert server.to_dict()['port'] == 8001
    assert export_payload.to_dict()['service'] == 'Provider-V2'


def test_dependencies_defaults() -> None:
    portable = get_portable_settings()
    server = get_server_config()
    assert portable.theme == 'auto'
    assert isinstance(server.port, int)


def test_summarize_for_client_defaults() -> None:
    payload = summarize_for_client({})
    assert payload['service'] == 'Provider-V2'
    assert payload['models'] == []
    assert payload['platforms'] == {}


def test_make_json_download_name() -> None:
    name = make_json_download_name('summary')
    assert name.startswith('summary_')
    assert name.endswith('.json')
