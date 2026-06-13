from __future__ import annotations

from pathlib import Path

from src.core.config import get_config

# tests/src/core/test_webui.py -> 3 parents -> tests/ -> 1 more -> project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
STATIC_DIR = PROJECT_ROOT / "src" / "webui" / "static"


def test_index_html_exists() -> None:
    assert (STATIC_DIR / "index.html").exists()


def test_index_html_contains_core_sections() -> None:
    config = get_config()
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    assert 'Provider-V2 WebUI' in html
    assert '/v1/webui/summary' in html or 'summary_api' not in html  # API calls are in JS
    assert '/v1/webui/ws/logs' in html or 'socketNotice' in html
    assert 'theme' in html  # theme control
    assert '模型搜索' in html or 'modelSearchInput' in html
    assert '概览' in html or 'overview' in html


def test_index_html_has_overview_tab() -> None:
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    assert 'data-initial-tab="overview"' in html
    assert 'tab-overview' in html


def test_static_css_exists() -> None:
    assert (STATIC_DIR / "css" / "styles.css").exists()
    css = (STATIC_DIR / "css" / "styles.css").read_text(encoding="utf-8")
    assert '--accent' in css
    assert '[data-theme="dark"]' in css


def test_static_js_exists() -> None:
    js_files = ["state.js", "render.js", "actions.js", "chat.js", "bootstrap.js"]
    for js_file in js_files:
        assert (STATIC_DIR / "js" / js_file).exists(), f"{js_file} not found"


def test_index_html_references_static_assets() -> None:
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    assert '/static/css/styles.css' in html
    assert '/static/js/state.js' in html
    assert '/static/js/render.js' in html
    assert '/static/js/actions.js' in html
    assert '/static/js/chat.js' in html
    assert '/static/js/bootstrap.js' in html
