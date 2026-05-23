from __future__ import annotations

"""WebUI 模板片段。"""

from typing import Iterable, List

from src.webui.models import DocSection

__all__ = [
    "render_doc_sections",
    "render_nav_items",
    "render_metrics_template",
    "render_platform_template",
]


def render_nav_items() -> str:
    """渲染垂直侧栏导航标签。"""
    items = [
        ("overview", "📊 概览"),
        ("platforms", "🔌 平台"),
        ("models", "🧠 模型"),
        ("docs", "📖 文档"),
        ("config", "⚙️ 配置"),
        ("logs", "📋 日志"),
    ]
    return "".join(
        '<button class="sidebar-nav-item tab-button" data-tab="{}" type="button">{}</button>'.format(key, label)
        for key, label in items
    )


def render_doc_sections(sections: Iterable[DocSection]) -> str:
    """渲染在线文档卡片。"""
    blocks: List[str] = []
    for section in sections:
        items_html = "".join(
            (
                '<a class="grid gap-1 no-underline leading-snug rounded-[10px] border border-border bg-panel text-text px-3 py-2.5 text-[14px] hover:bg-panel-alt transition" href="{href}">'
                '<strong>{title}</strong>'
                '<span class="text-muted text-[13px]">{description}</span>'
                '</a>'
            ).format(
                href=item.href,
                title=item.title,
                description=item.description,
            )
            for item in section.items
        )
        blocks.append(
            '<section class="grid gap-2.5"><h3 class="text-[13px] text-muted m-0 mb-2">{}</h3><div class="grid gap-2.5">{}</div></section>'.format(
                section.title,
                items_html,
            )
        )
    return "".join(blocks)


def render_metrics_template() -> str:
    """渲染指标卡模板。"""
    return """<div class="grid gap-3 grid-cols-[repeat(auto-fit,minmax(170px,1fr))]">
        <div class="border border-border rounded-[14px] p-3.5 bg-panel-alt"><div class="text-[13px] text-muted m-0 mb-2">平台数量</div><div class="text-2xl font-bold" id="platformCount">-</div></div>
        <div class="border border-border rounded-[14px] p-3.5 bg-panel-alt"><div class="text-[13px] text-muted m-0 mb-2">模型数量</div><div class="text-2xl font-bold" id="modelCount">-</div></div>
        <div class="border border-border rounded-[14px] p-3.5 bg-panel-alt"><div class="text-[13px] text-muted m-0 mb-2">可用平台</div><div class="text-2xl font-bold" id="availablePlatformCount">-</div></div>
        <div class="border border-border rounded-[14px] p-3.5 bg-panel-alt"><div class="text-[13px] text-muted m-0 mb-2">最近刷新</div><div class="text-2xl font-bold" id="lastRefresh">-</div></div>
        <div class="border border-border rounded-[14px] p-3.5 bg-panel-alt"><div class="text-[13px] text-muted m-0 mb-2">服务状态</div><div class="text-2xl font-bold" id="healthValue">-</div></div>
      </div>"""


def render_platform_template() -> str:
    """渲染平台搜索与列表模板。"""
    return """<div class="flex flex-wrap justify-between items-end gap-3">
        <div>
          <h2>平台状态</h2>
          <p class="m-0 text-muted leading-relaxed">支持按平台名筛选，并查看候选数、可用数、模型数和上下文长度。</p>
        </div>
        <label class="grid gap-1.5 min-w-[220px]" for="platformSearchInput">
          <span class="text-xs text-muted">筛选平台</span>
          <input id="platformSearchInput" type="search" placeholder="输入平台名" class="rounded-[10px] border border-border bg-panel text-text px-3 py-2.5 text-[14px]">
        </label>
      </div>
      <div class="grid gap-3 grid-cols-[repeat(auto-fit,minmax(240px,1fr))]" id="platformGrid"></div>"""
