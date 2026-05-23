from __future__ import annotations

from src.core.config import get_config
from src.webui import render_webui


def test_render_webui_contains_core_sections() -> None:
    config = get_config()
    html = render_webui()
    assert 'Provider-V2 WebUI' in html
    assert '/v1/webui/summary' in html
    assert '/v1/webui/ws/logs' in html
    assert '切换主题' in html
    assert '在线文档' in html
    assert '管理视图' in html
    assert '导出摘要' in html
    assert '模型搜索' in html
    assert config.server.version in html


def test_render_docs_uses_docs_tab() -> None:
    html = render_webui(page='docs')
    assert 'tab-docs' in html
    assert 'OpenAI 兼容接口' in html
    assert 'Anthropic 兼容接口' in html
