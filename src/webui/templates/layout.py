from __future__ import annotations

"""WebUI 页面布局模板。"""

from src.webui.services import build_doc_sections
from src.webui.templates.scripts import WEBUI_SCRIPTS
from src.webui.templates.sections import (
    render_doc_sections,
    render_metrics_template,
    render_nav_items,
    render_platform_template,
)

__all__ = ["render_document"]


def render_document(*, version: str, host: str, port: int, initial_tab: str) -> str:
    """渲染 WebUI HTML。"""
    return (
        _HTML_TEMPLATE.replace("__VERSION__", version)
        .replace("__HOST__", host)
        .replace("__PORT__", str(port))
        .replace("__NAV_ITEMS__", render_nav_items())
        .replace("__METRICS__", render_metrics_template())
        .replace("__PLATFORM_BLOCK__", render_platform_template())
        .replace("__DOC_SECTIONS__", render_doc_sections(build_doc_sections()))
        .replace("__SCRIPTS__", WEBUI_SCRIPTS)
        .replace("__INITIAL_TAB__", initial_tab)
    )


_HTML_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Provider-V2 WebUI</title>
  <style>
    :root {
      color-scheme: light dark;
      --bg: #f3f6fb; --panel: #ffffff; --panel-alt: #eef3ff;
      --panel-soft: #f9fbff; --text: #162033; --muted: #5d6980;
      --accent: #4263eb; --accent-soft: rgba(66, 99, 235, 0.12);
      --ok: #1f9d61; --warn: #d17b17; --err: #d94848;
      --border: #d7deec; --shadow: 0 12px 32px rgba(21, 33, 56, 0.08);
    }
    [data-theme="dark"] {
      --bg: #0d1420; --panel: #172131; --panel-alt: #1d2a3d;
      --panel-soft: #131d2c; --text: #edf3ff; --muted: #9eabc2;
      --accent: #8aa4ff; --accent-soft: rgba(138, 164, 255, 0.16);
      --ok: #37ca7e; --warn: #ffb454; --err: #ff7b7b;
      --border: #2b3a52; --shadow: none;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: Arial, sans-serif;
      background: linear-gradient(180deg, var(--bg) 0%, var(--panel-soft) 100%); color: var(--text); }
    .tab-panel.active { display: grid; gap: 14px; }
    .tab-button.active { background: var(--accent); color: #fff; border-color: transparent; }
    .webui-layout { display: grid; grid-template-columns: 180px 1fr; min-height: 60vh; }
    .webui-sidebar { display: grid; gap: 4px; padding: 14px; border-right: 1px solid var(--border);
      background: var(--panel-soft); position: sticky; top: 0; max-height: 80vh; overflow-y: auto; }
    .sidebar-nav-item { text-align: left; border-radius: 10px; padding: 10px 14px; font-size: 14px;
      border: 1px solid transparent; background: var(--panel); color: var(--text);
      cursor: pointer; transition: all 0.15s; font-weight: 500; }
    .sidebar-nav-item:hover { background: var(--panel-alt); }
    .sidebar-nav-item.active { background: var(--accent-soft); color: var(--accent);
      border-color: var(--accent); font-weight: 600; border-left: 3px solid var(--accent); }
    .webui-content { padding: 14px; min-width: 0; }
    .config-edit-area { min-height: 200px; max-height: 500px; overflow: auto;
      font-family: 'Courier New', monospace; font-size: 13px; line-height: 1.6;
      border: 1px solid var(--border); border-radius: 12px; padding: 12px;
      background: var(--panel-soft); color: var(--text); white-space: pre; word-break: break-all;
      width: 100%; resize: vertical; }
    .config-edit-area:focus { border-color: var(--accent); outline: none; }
    .status-saved { color: var(--ok); font-size: 12px; font-weight: 600; }
    .status-dirty { color: var(--warn); font-size: 12px; font-weight: 600; }
    #reloadServerButton { border-color: var(--warn); color: var(--warn); }
    #reloadServerButton:hover { background: var(--warn); color: #fff; }
    @media (max-width: 768px) {
      .webui-layout { grid-template-columns: 1fr; }
      .webui-sidebar { display: none; position: fixed; top: 0; left: 0;
        width: 240px; height: 100vh; z-index: 1000; padding: 60px 12px 12px;
        box-shadow: var(--shadow); }
      .webui-sidebar.open { display: grid; }
    }
  </style>
</head>
<body>
  <div class="max-w-[1440px] mx-auto p-3 md:p-4 grid gap-4">
    <section class="bg-panel border border-border rounded-[18px] shadow-panel p-5 grid gap-4">
      <div class="grid gap-3 md:grid-cols-[1fr_auto] items-start">
        <div>
          <h1 class="text-[30px] font-bold m-0">Provider-V2 WebUI</h1>
          <p class="m-0 text-muted leading-relaxed">生产化内置管理台，覆盖概览、平台状态、模型清单、在线文档、配置管理与日志反馈。</p>
        </div>
        <div class="flex flex-wrap gap-2 justify-end">
          <span class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1.5 text-xs bg-accent-soft text-text">版本 __VERSION__</span>
          <span class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1.5 text-xs bg-accent-soft text-text">__HOST__:__PORT__</span>
          <span class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1.5 text-xs bg-accent-soft text-text" id="themeState">theme: auto</span>
          <span class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1.5 text-xs bg-accent-soft text-text" id="refreshState">refresh: manual</span>
        </div>
      </div>
      <div class="grid gap-3 grid-cols-[repeat(auto-fit,minmax(130px,1fr))]">
        <button class="cursor-pointer font-bold rounded-lg px-4 py-2.5 text-[14px] bg-accent text-white border border-transparent hover:opacity-90 transition" id="refreshButton" type="button">刷新状态</button>
        <button class="cursor-pointer font-bold rounded-lg px-4 py-2.5 text-[14px] border border-border bg-panel text-text hover:bg-panel-alt transition" id="refreshModelsButton" type="button">刷新模型缓存</button>
        <button class="cursor-pointer font-bold rounded-lg px-4 py-2.5 text-[14px] border border-border bg-panel text-text hover:bg-panel-alt transition" id="portableButton" type="button">便携设置</button>
        <button class="cursor-pointer font-bold rounded-lg px-4 py-2.5 text-[14px] border border-warn text-warn bg-panel hover:bg-warn hover:text-white transition" id="reloadServerButton" type="button">重启服务</button>
        <button class="cursor-pointer font-bold rounded-lg px-4 py-2.5 text-[14px] border border-border bg-panel text-text hover:bg-panel-alt transition" id="reloadConfigButton" type="button">重载配置</button>
      </div>
      __METRICS__
      <div class="flex flex-wrap gap-2 items-center">
        <div class="border-l-4 border-accent px-3 py-2.5 bg-accent-soft rounded-[10px] leading-relaxed text-[14px]">该页面优先使用只读摘要接口，单个接口失败时会自动降级，不会导致整页失效。</div>
        <div class="border-l-4 border-accent px-3 py-2.5 bg-accent-soft rounded-[10px] leading-relaxed text-[14px]" id="socketNotice">日志 WebSocket: /v1/webui/ws/logs</div>
      </div>
    </section>

    <section class="bg-panel border border-border rounded-[18px] shadow-panel p-[18px] grid gap-[14px] hidden" id="portablePanel">
      <div class="flex flex-wrap justify-between items-end gap-3">
        <div>
          <h2>便携设置</h2>
          <p class="m-0 text-muted leading-relaxed">这些设置保存在浏览器本地，适合便携环境与临时运行环境。</p>
        </div>
      </div>
      <div class="grid gap-3 grid-cols-[repeat(auto-fit,minmax(240px,1fr))]">
        <label class="border border-border rounded-[14px] p-3.5 bg-panel-alt">
          <div class="text-[13px] text-muted m-0 mb-2">主题模式</div>
          <select id="themeSelect" class="rounded-[10px] border border-border bg-panel text-text px-3 py-2.5 text-[14px]">
            <option value="auto">auto</option>
            <option value="light">light</option>
            <option value="dark">dark</option>
          </select>
        </label>
        <label class="border border-border rounded-[14px] p-3.5 bg-panel-alt">
          <div class="text-[13px] text-muted m-0 mb-2">自动刷新间隔（秒）</div>
          <input id="refreshIntervalInput" type="number" min="0" max="300" step="5" class="rounded-[10px] border border-border bg-panel text-text px-3 py-2.5 text-[14px]">
        </label>
        <label class="border border-border rounded-[14px] p-3.5 bg-panel-alt">
          <div class="text-[13px] text-muted m-0 mb-2">请求超时（毫秒）</div>
          <input id="timeoutInput" type="number" min="500" max="30000" step="500" class="rounded-[10px] border border-border bg-panel text-text px-3 py-2.5 text-[14px]">
        </label>
        <label class="border border-border rounded-[14px] p-3.5 bg-panel-alt">
          <div class="text-[13px] text-muted m-0 mb-2">显示紧凑模式</div>
          <select id="compactSelect" class="rounded-[10px] border border-border bg-panel text-text px-3 py-2.5 text-[14px]">
            <option value="0">关闭</option>
            <option value="1">开启</option>
          </select>
        </label>
      </div>
      <p class="m-0 text-muted leading-relaxed">设置不写回服务端配置文件，避免对线上进程产生意外副作用。</p>
    </section>

    <section class="bg-panel border border-border rounded-[18px] shadow-panel grid gap-0 overflow-hidden">
      <div class="webui-layout">
        <aside class="webui-sidebar" id="sidebar">
          __NAV_ITEMS__
        </aside>
        <main class="webui-content">

      <section class="tab-panel hidden" id="tab-overview" aria-labelledby="tab-overview-button">
        <div class="flex flex-wrap justify-between items-end gap-3">
          <div>
            <h2>运行概览</h2>
            <p class="m-0 text-muted leading-relaxed">显示服务、并发策略、代理、鉴权和启动开关摘要。</p>
          </div>
          <div class="flex flex-wrap gap-2">
            <button class="tab-button cursor-pointer font-bold rounded-lg px-4 py-2.5 border border-border bg-panel text-text hover:bg-panel-alt transition" id="exportSummaryButton" type="button">导出摘要</button>
            <button class="tab-button cursor-pointer font-bold rounded-lg px-4 py-2.5 border border-border bg-panel text-text hover:bg-panel-alt transition" id="copySummaryButton" type="button">复制摘要</button>
          </div>
        </div>
        <div class="border-l-4 border-accent px-3 py-2.5 bg-accent-soft rounded-[10px] leading-relaxed text-[14px]" id="overviewNotice">等待状态刷新后展示摘要提示。</div>
        <div class="grid gap-3 grid-cols-[repeat(auto-fit,minmax(240px,1fr))]" id="overviewGrid"></div>
      </section>

      <section class="tab-panel hidden" id="tab-platforms" aria-labelledby="tab-platforms-button">
        __PLATFORM_BLOCK__
      </section>

      <section class="tab-panel hidden" id="tab-models" aria-labelledby="tab-models-button">
        <div class="flex flex-wrap justify-between items-end gap-3">
          <div>
            <h2>模型清单</h2>
            <p class="m-0 text-muted leading-relaxed">支持按名称、平台和能力筛选模型，展示来源平台、上下文长度和能力简表。</p>
          </div>
          <div class="grid gap-3 grid-cols-[repeat(auto-fit,minmax(240px,1fr))]">
            <label class="border border-border rounded-[14px] p-3.5 bg-panel-alt">
              <div class="text-[13px] text-muted m-0 mb-2">模型搜索</div>
              <input id="modelSearchInput" type="search" placeholder="输入模型名" class="rounded-[10px] border border-border bg-panel text-text px-3 py-2.5 text-[14px]">
            </label>
            <label class="border border-border rounded-[14px] p-3.5 bg-panel-alt">
              <div class="text-[13px] text-muted m-0 mb-2">平台筛选</div>
              <select id="modelPlatformSelect" class="rounded-[10px] border border-border bg-panel text-text px-3 py-2.5 text-[14px]"><option value="">全部平台</option></select>
            </label>
            <label class="border border-border rounded-[14px] p-3.5 bg-panel-alt">
              <div class="text-[13px] text-muted m-0 mb-2">能力筛选</div>
              <select id="modelCapabilitySelect" class="rounded-[10px] border border-border bg-panel text-text px-3 py-2.5 text-[14px]"><option value="">全部能力</option></select>
            </label>
          </div>
        </div>
        <div class="grid gap-3 grid-cols-[repeat(auto-fit,minmax(240px,1fr))]" id="modelGrid"></div>
      </section>

      <section class="tab-panel hidden" id="tab-docs" aria-labelledby="tab-docs-button">
        <div class="flex flex-wrap justify-between items-end gap-3">
          <div>
            <h2>在线文档</h2>
            <p class="m-0 text-muted leading-relaxed">集中查看协议入口、管理接口和常用只读地址。</p>
          </div>
        </div>
        __DOC_SECTIONS__
      </section>

      <section class="tab-panel hidden" id="tab-config" aria-labelledby="tab-config-button">
        <div class="flex flex-wrap justify-between items-end gap-3">
          <div>
            <h2>配置管理</h2>
            <p class="m-0 text-muted leading-relaxed">在线编辑配置文件，修改后自动保存并重新加载。</p>
          </div>
          <div class="flex flex-wrap gap-2">
            <button class="tab-button cursor-pointer font-bold rounded-lg px-4 py-2.5 border border-border bg-panel text-text hover:bg-panel-alt transition" id="configEditToggle" type="button">编辑配置</button>
            <button class="tab-button cursor-pointer font-bold rounded-lg px-4 py-2.5 border border-border bg-panel text-text hover:bg-panel-alt transition" id="copyConfigButton" type="button">复制配置</button>
            <span id="configSaveStatus" class="status-saved flex items-center">已保存</span>
          </div>
        </div>
        <div class="grid gap-3 grid-cols-[repeat(auto-fit,minmax(240px,1fr))]" id="configGrid"></div>
        <div class="min-h-[140px] max-h-[260px] overflow-auto whitespace-pre-wrap font-mono text-[13px] leading-relaxed border border-border rounded-xl p-3 bg-panel-soft" id="configJsonBox"></div>
        <textarea class="config-edit-area hidden" id="configEditArea" spellcheck="false" aria-label="配置编辑器"></textarea>
      </section>

      <section class="tab-panel hidden" id="tab-logs" aria-labelledby="tab-logs-button">
        <div class="flex flex-wrap justify-between items-end gap-3">
          <div>
            <h2>运行日志</h2>
            <p class="m-0 text-muted leading-relaxed">显示当前页面交互与接口调用反馈，不替代服务端真实日志文件。</p>
          </div>
          <div class="flex flex-wrap gap-2">
            <button class="tab-button cursor-pointer font-bold rounded-lg px-4 py-2.5 border border-border bg-panel text-text hover:bg-panel-alt transition" id="clearLogButton" type="button">清空日志</button>
          </div>
        </div>
        <div class="min-h-[140px] max-h-[260px] overflow-auto whitespace-pre-wrap font-mono text-[13px] leading-relaxed border border-border rounded-xl p-3 bg-panel-soft" id="logBox"></div>
      </section>

        </main>
      </div>
    </section>
  </div>

  <div class="fixed right-4 bottom-4 grid gap-2 z-[1000]" id="toastWrap" aria-live="polite"></div>

  <button id="fabThemeButton" type="button"
    class="fixed bottom-5 right-5 w-12 h-12 rounded-full bg-blue-600 text-white shadow-lg hover:scale-110 transition-transform z-[1001] flex items-center justify-center text-xl"
    aria-label="切换主题">
    <span id="fabThemeIcon">&#9790;</span>
  </button>

  <script>
__SCRIPTS__
  </script>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: ['selector', '[data-theme="dark"]'],
      theme: {
        extend: {
          colors: {
            bg: 'var(--bg)',
            panel: 'var(--panel)',
            'panel-alt': 'var(--panel-alt)',
            'panel-soft': 'var(--panel-soft)',
            text: 'var(--text)',
            muted: 'var(--muted)',
            accent: 'var(--accent)',
            'accent-soft': 'var(--accent-soft)',
            ok: 'var(--ok)',
            warn: 'var(--warn)',
            err: 'var(--err)',
            border: 'var(--border)',
          },
          boxShadow: { panel: 'var(--shadow)' },
        }
      }
    };
  </script>
</body>
</html>
"""
