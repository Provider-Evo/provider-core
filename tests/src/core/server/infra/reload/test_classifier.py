from __future__ import annotations

from src.core.server.infra.reload.classifier import classify_paths


def test_classify_platform() -> None:
    result = classify_paths({r"X:\proj\src\platforms\qwen\core\client.py"})
    assert result.process is False
    assert result.platforms == frozenset({"qwen"})


def test_classify_routes_application() -> None:
    result = classify_paths({r"X:\proj\src\routes\openai\helpers.py"})
    assert result.process is False
    assert result.application is True


def test_classify_core_process() -> None:
    result = classify_paths({r"X:\proj\src\core\server\infra\reload\coordinator.py"})
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
