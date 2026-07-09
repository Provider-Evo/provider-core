from __future__ import annotations

import pytest

from src.core.server.reload.classifier import classify_paths
from src.core.server.plugins.plugin_catalog import resolve_platform_plugin_id
from src.foundation.paths import project_root


def test_classify_platform() -> None:
    result = classify_paths({r"X:\proj\src\platforms\qwen\core\client.py"})
    assert result.process is False
    plugin_id = resolve_platform_plugin_id("qwen")
    if plugin_id:
        assert plugin_id in result.plugins
    else:
        assert result.platforms == frozenset({"qwen"})


def test_classify_routes_application() -> None:
    result = classify_paths({r"X:\proj\src\routes\openai\helpers.py"})
    assert result.process is False
    assert result.application is True


def test_classify_core_process() -> None:
    result = classify_paths({r"X:\proj\src\core\server\reload\coordinator.py"})
    assert result.process is True


def test_classify_core_server_application() -> None:
    result = classify_paths({r"X:\proj\src\core\server\app.py"})
    assert result.process is False
    assert result.application is True


def test_classify_dispatch_application() -> None:
    result = classify_paths({r"X:\proj\src\core\dispatch\registry.py"})
    assert result.process is False
    assert result.application is True


def test_classify_static() -> None:
    result = classify_paths({r"X:\proj\src\webui\static\ui\bootstrap.js"})
    assert result.process is False
    assert result.static is True


def test_classify_webui_py_application() -> None:
    result = classify_paths({r"X:\proj\src\webui\routers\api\summary.py"})
    assert result.process is False
    assert result.application is True


def test_classify_main_py_process() -> None:
    result = classify_paths({r"X:\proj\main.py"})
    assert result.process is True


def test_classify_plugin_reload() -> None:
    path = (
        project_root
        / "plugins"
        / "Provider-Coplan-Util"
        / "provider_coplan_util"
        / "templates.py"
    )
    if not path.is_file():
        pytest.skip("coplan plugin not present")
    result = classify_paths({str(path)})
    assert result.process is False
    assert result.plugins == frozenset({"nichengfuben.provider-coplan-util"})
    assert result.plugin_app_reload is True


def test_classify_platform_plugin_no_app_reload() -> None:
    path = (
        project_root
        / "plugins"
        / "Provider-Qwen-Adapter"
        / "provider_qwen"
        / "core"
        / "client.py"
    )
    if not path.is_file():
        pytest.skip("qwen plugin not present")
    result = classify_paths({str(path)})
    assert result.process is False
    assert "qwen" in str(result.plugins).lower() or result.plugins
    assert result.plugin_app_reload is False


def test_classify_plugin_static_l0() -> None:
    path = (
        project_root
        / "plugins"
        / "Provider-Webui-Util"
        / "static"
        / "index.html"
    )
    if not path.is_file():
        pytest.skip("webui plugin static not present")
    result = classify_paths({str(path)})
    assert result.process is False
    assert result.static is True
    assert not result.plugins
    assert result.plugin_app_reload is False


def test_classify_plugin_manifest_triggers_app_reload() -> None:
    path = project_root / "plugins" / "Provider-Fncall-Util" / "_manifest.json"
    if not path.is_file():
        pytest.skip("fncall manifest not present")
    result = classify_paths({str(path)})
    assert result.process is False
    assert result.plugins
    assert result.plugin_app_reload is True
